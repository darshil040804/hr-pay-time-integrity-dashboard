"""Generate the synthetic HR dataset and plant known defects.

All data is fictional. Table and column design is modeled on SAP HCM
structures (OM, PA, Time Management, Payroll), but nothing here comes from a
real SAP system or a real organization.

Run from the repo root:
    python -m data.generate

Steps:
1. generate_clean() builds a fully consistent dataset (every validation rule
   should return zero exceptions on it).
2. plant_defects() copies that dataset and plants an exact, known number of
   defects per rule. Each defect uses its own employees/positions so that one
   planted defect never trips a different rule.
3. The defective dataset is written to data/*.csv and the planted counts to
   data/planted_defects.csv, the single source of truth for the tests.

Both steps use fixed seeds, so the output is identical on every run.
"""

import copy
import random
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from faker import Faker

# Allow "python data/generate.py" as well as "python -m data.generate".
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.schema import END_OF_TIME, SCHEMA, coerce  # noqa: E402

SEED = 42
DATA_DIR = Path(__file__).resolve().parent

N_EMPLOYEES = 500
N_TERMINATED = 25          # all terminated before the pay periods start
N_VACANT_POSITIONS = 40    # active positions with nobody in them
N_INACTIVE_POSITIONS = 20  # closed positions with nobody in them
FIRST_PERIOD_START = date(2026, 1, 5)  # a Monday
N_PERIODS = 6

# Planted defects per rule. Written to planted_defects.csv.
PLANTED = {
    "OP-01": 6, "OP-02": 4, "OP-03": 3, "OP-04": 5, "OP-05": 5,
    "TP-01": 8, "TP-02": 4, "TP-03": 5, "TP-04": 6, "TP-05": 4, "TP-06": 3,
}

# --- Reference data ---------------------------------------------------------

# 1 root + 5 divisions + 34 departments = 40 org units.
DIVISIONS = {
    "Academic Affairs": [
        "College of Engineering", "College of Arts & Letters", "College of Natural Science",
        "College of Business", "College of Education", "College of Nursing",
        "University Library", "Office of the Registrar",
    ],
    "Finance & Administration": [
        "Payroll Office", "Human Resources", "Budget Office", "Procurement",
        "Accounts Payable", "IT Services", "Internal Audit",
    ],
    "Student Affairs": [
        "Admissions", "Financial Aid", "Residence Life", "Dining Services",
        "Career Services", "Counseling Center", "Recreation Services",
    ],
    "Facilities": [
        "Grounds", "Custodial Services", "Building Maintenance", "Utilities",
        "Campus Safety", "Transportation",
    ],
    "Research": [
        "Sponsored Programs", "Research Compliance", "Animal Care",
        "Research Computing", "Technology Transfer", "Core Facilities",
    ],
}
COLLEGES = DIVISIONS["Academic Affairs"][:6]  # where faculty work

# job_id: (title, flsa_status, employee_group, hourly rate range)
JOBS = {
    "JOB01": ("Professor", "Exempt", "Faculty", (55, 80)),
    "JOB02": ("Associate Professor", "Exempt", "Faculty", (45, 60)),
    "JOB03": ("Assistant Professor", "Exempt", "Faculty", (38, 50)),
    "JOB04": ("Lecturer", "Exempt", "Faculty", (30, 40)),
    "JOB05": ("HR Generalist", "Exempt", "Support Staff", (28, 38)),
    "JOB06": ("Payroll Specialist", "Non-exempt", "Support Staff", (24, 32)),
    "JOB07": ("Accountant", "Exempt", "Support Staff", (30, 42)),
    "JOB08": ("Administrative Assistant", "Non-exempt", "Support Staff", (19, 26)),
    "JOB09": ("IT Analyst", "Exempt", "Support Staff", (35, 50)),
    "JOB10": ("Custodian", "Non-exempt", "Support Staff", (16, 21)),
    "JOB11": ("Groundskeeper", "Non-exempt", "Support Staff", (17, 22)),
    "JOB12": ("Maintenance Technician", "Non-exempt", "Support Staff", (22, 30)),
    "JOB13": ("Office Manager", "Exempt", "Support Staff", (27, 36)),
    "JOB14": ("Student Services Coordinator", "Non-exempt", "Support Staff", (20, 27)),
    "JOB15": ("Campus Safety Officer", "Non-exempt", "Support Staff", (23, 31)),
    "JOB16": ("Temporary Clerk", "Non-exempt", "Temporary", (15, 19)),
    "JOB17": ("Seasonal Worker", "Non-exempt", "Temporary", (15, 18)),
    "JOB18": ("Food Service Worker", "Non-exempt", "Temporary", (15, 19)),
}
# Jobs that work evening/night shifts and can earn shift differential.
SHIFT_JOBS = {"JOB10", "JOB15", "JOB18"}
SHIFT_DIFFERENTIAL_RATE = 1.50  # dollars per hour on top of regular pay

WAGE_TYPES = [
    ("1000", "Regular Pay", "Both"),
    ("1100", "Overtime Pay", "Non-exempt"),
    ("1200", "Vacation Pay", "Both"),
    ("1300", "Sick Pay", "Both"),
    ("1400", "Shift Differential", "Non-exempt"),
]
ATTENDANCE_TO_WAGE_TYPE = {"Regular": "1000", "Overtime": "1100", "Vacation": "1200", "Sick": "1300"}
OVERTIME_MULTIPLIER = 1.5


# --- Clean data -------------------------------------------------------------

def generate_clean(seed: int = SEED) -> dict[str, pd.DataFrame]:
    """Build a consistent dataset with no defects. Returns {table: DataFrame}."""
    rng = random.Random(seed)
    fake = Faker("en_US")
    fake.seed_instance(seed)

    # Org units (similar to SAP OM object type O)
    org_rows = [("ORG001", "Example University (fictional)", None)]
    dept_ids = {}  # department name -> org_unit_id
    n = 2
    for division, departments in DIVISIONS.items():
        div_id = f"ORG{n:03d}"
        org_rows.append((div_id, division, "ORG001"))
        n += 1
        for dept in departments:
            dept_ids[dept] = f"ORG{n:03d}"
            org_rows.append((dept_ids[dept], dept, div_id))
            n += 1
    org_units = pd.DataFrame(org_rows, columns=["org_unit_id", "name", "parent_org_unit_id"])
    org_units["valid_from"] = "2020-01-01"
    org_units["valid_to"] = END_OF_TIME

    # Jobs (similar to SAP OM object type C)
    jobs = pd.DataFrame(
        [(job_id, title, flsa) for job_id, (title, flsa, _, _) in JOBS.items()],
        columns=["job_id", "title", "flsa_status"],
    )

    # Employees and the positions they hold (one position per active employee)
    jobs_by_group = {}
    for job_id, (_, _, group, _) in JOBS.items():
        jobs_by_group.setdefault(group, []).append(job_id)
    all_depts = list(dept_ids)

    employees, positions, rates = [], [], {}
    pos_n = 1
    for i in range(N_EMPLOYEES):
        emp_id = 100001 + i
        group = rng.choices(["Faculty", "Support Staff", "Temporary"], weights=[25, 60, 15])[0]
        job_id = rng.choice(jobs_by_group[group])
        title, flsa, _, (low, high) = JOBS[job_id]
        dept = rng.choice(COLLEGES) if group == "Faculty" else rng.choice(all_depts)
        if group == "Temporary":
            weekly = rng.choice([20.0, 30.0])
        elif group == "Support Staff":
            weekly = rng.choices([40.0, 30.0, 20.0], weights=[85, 10, 5])[0]
        else:
            weekly = 40.0
        rates[emp_id] = round(rng.uniform(low, high), 2)

        terminated = i >= N_EMPLOYEES - N_TERMINATED
        hire_date = fake.date_between(date(2008, 1, 1), date(2025, 6, 30))
        if terminated:
            # Terminated before the first pay period; they hold no position.
            term_date = fake.date_between(max(hire_date, date(2025, 7, 1)), date(2025, 12, 31))
            position_id = None
        else:
            term_date = None
            position_id = f"POS{pos_n:04d}"
            positions.append((position_id, dept_ids[dept], job_id, "Active",
                              min(hire_date, date(2020, 1, 1)).isoformat(), END_OF_TIME))
            pos_n += 1

        employees.append({
            "emp_id": emp_id,
            "first_name": fake.first_name(),
            "last_name": fake.last_name(),
            "position_id": position_id,
            "employee_group": group,
            "employee_subgroup": "Salaried" if flsa == "Exempt" else "Hourly",
            "weekly_scheduled_hours": weekly,
            "status": "Terminated" if terminated else "Active",
            "hire_date": hire_date.isoformat(),
            "term_date": term_date.isoformat() if term_date else None,
        })

    # Vacant positions (active, unfilled) and closed positions (inactive, unfilled)
    for _ in range(N_VACANT_POSITIONS):
        positions.append((f"POS{pos_n:04d}", dept_ids[rng.choice(all_depts)], rng.choice(list(JOBS)),
                          "Active", "2024-07-01", END_OF_TIME))
        pos_n += 1
    for _ in range(N_INACTIVE_POSITIONS):
        positions.append((f"POS{pos_n:04d}", dept_ids[rng.choice(all_depts)], rng.choice(list(JOBS)),
                          "Inactive", "2020-01-01", "2025-06-30"))
        pos_n += 1
    positions = pd.DataFrame(positions, columns=list(SCHEMA["positions"]))
    employees = pd.DataFrame(employees)

    wage_types = pd.DataFrame(WAGE_TYPES, columns=list(SCHEMA["wage_types"]))

    # Pay periods: biweekly, paid the Friday after the period ends
    periods = []
    for p in range(N_PERIODS):
        start = FIRST_PERIOD_START + timedelta(days=14 * p)
        end = start + timedelta(days=13)
        periods.append((f"PP{p + 1:02d}", start, end, end + timedelta(days=5)))
    pay_periods = pd.DataFrame(periods, columns=list(SCHEMA["pay_periods"]))

    # Time entries: one entry per scheduled workday for every active employee,
    # with occasional vacation/sick days and (non-exempt only) overtime.
    job_of = dict(zip(positions["position_id"], positions["job_id"]))
    time_rows = []
    for emp in employees[employees["status"] == "Active"].itertuples():
        exempt = JOBS[job_of[emp.position_id]][1] == "Exempt"
        daily = emp.weekly_scheduled_hours / 5
        for _, start, end, _ in periods:
            day = start
            while day <= end:
                if day.weekday() < 5:
                    roll = rng.random()
                    kind = "Vacation" if roll < 0.03 else "Sick" if roll < 0.05 else "Regular"
                    time_rows.append((emp.emp_id, day, daily, kind))
                    if kind == "Regular" and not exempt and rng.random() < 0.08:
                        time_rows.append((emp.emp_id, day, rng.choice([1.0, 1.5, 2.0, 3.0]), "Overtime"))
                day += timedelta(days=1)
    time_entries = pd.DataFrame(time_rows, columns=list(SCHEMA["time_entries"]))

    # Payroll results: paid hours per wage type = recorded hours per attendance type
    period_of = {}
    for period_id, start, end, _ in periods:
        for d in range(14):
            period_of[start + timedelta(days=d)] = period_id
    pay_date = {period_id: pd_ for period_id, _, _, pd_ in periods}

    summary = (time_entries.assign(period_id=time_entries["work_date"].map(period_of))
               .groupby(["period_id", "emp_id", "attendance_type"], as_index=False)["hours"].sum())
    shift_workers = {
        emp.emp_id for emp in employees[employees["status"] == "Active"].itertuples()
        if job_of[emp.position_id] in SHIFT_JOBS and rng.random() < 0.5
    }
    pay_rows = []
    for row in summary.itertuples():
        rate = rates[row.emp_id] * (OVERTIME_MULTIPLIER if row.attendance_type == "Overtime" else 1)
        pay_rows.append((row.period_id, row.emp_id, ATTENDANCE_TO_WAGE_TYPE[row.attendance_type],
                         row.hours, round(row.hours * rate, 2), pay_date[row.period_id]))
        if row.attendance_type == "Regular" and row.emp_id in shift_workers:
            pay_rows.append((row.period_id, row.emp_id, "1400", row.hours,
                             round(row.hours * SHIFT_DIFFERENTIAL_RATE, 2), pay_date[row.period_id]))
    payroll_results = pd.DataFrame(pay_rows, columns=list(SCHEMA["payroll_results"]))

    tables = {
        "org_units": org_units, "jobs": jobs, "positions": positions, "employees": employees,
        "wage_types": wage_types, "pay_periods": pay_periods,
        "time_entries": time_entries, "payroll_results": payroll_results,
    }
    return {name: _tidy(name, df) for name, df in tables.items()}


# --- Planted defects --------------------------------------------------------

def plant_defects(clean: dict[str, pd.DataFrame], seed: int = SEED) -> dict[str, pd.DataFrame]:
    """Return a copy of the clean dataset with PLANTED[rule] defects per rule.

    Every defect uses employees and positions not touched by any other defect
    (tracked in `used`), so each one trips exactly one rule.
    """
    rng = random.Random(seed)
    t = copy.deepcopy(clean)
    emp, pos, jobs = t["employees"], t["positions"], t["jobs"]
    periods = t["pay_periods"]
    used_emps, used_positions = set(), set()

    flsa_of_job = dict(zip(jobs["job_id"], jobs["flsa_status"]))
    job_of_pos = dict(zip(pos["position_id"], pos["job_id"]))
    active = emp[emp["status"] == "Active"]
    terminated = emp[emp["status"] == "Terminated"]

    def emp_flsa(emp_id):
        position_id = emp.loc[emp["emp_id"] == emp_id, "position_id"].iloc[0]
        return flsa_of_job[job_of_pos[position_id]]

    def pick_emps(candidates, n):
        """Pick n employees not yet used by another defect."""
        pool = sorted(set(candidates) - used_emps)
        chosen = rng.sample(pool, n)
        used_emps.update(chosen)
        return chosen

    def pick_period():
        return rng.choice(list(periods["period_id"]))

    def period_dates(period_id):
        row = periods[periods["period_id"] == period_id].iloc[0]
        return row["start_date"], row["end_date"], row["pay_date"]

    def adjust_pay(emp_id, period_id, wage_type, delta_hours):
        """Change a payroll line's hours by delta_hours, keeping its hourly rate."""
        pay = t["payroll_results"]
        mask = (pay["emp_id"] == emp_id) & (pay["period_id"] == period_id) & (pay["wage_type"] == wage_type)
        idx = pay.index[mask][0]
        rate = pay.at[idx, "amount"] / pay.at[idx, "hours"]
        pay.at[idx, "hours"] += delta_hours
        pay.at[idx, "amount"] = round(pay.at[idx, "hours"] * rate, 2)

    filled = set(active["position_id"])
    vacant = sorted(set(pos.loc[pos["status"] == "Active", "position_id"]) - filled)

    def pick_vacant(n):
        chosen = rng.sample(sorted(set(vacant) - used_positions), n)
        used_positions.update(chosen)
        return chosen

    # OP-01: active employee assigned to an inactive position.
    # Close the position of 6 active employees who are still in it.
    for emp_id in pick_emps(active["emp_id"], PLANTED["OP-01"]):
        position_id = emp.loc[emp["emp_id"] == emp_id, "position_id"].iloc[0]
        pos.loc[pos["position_id"] == position_id, ["status", "valid_to"]] = ["Inactive", date(2025, 12, 31)]
        used_positions.add(position_id)

    # OP-02: position with a missing or nonexistent org unit (vacant positions).
    for i, position_id in enumerate(pick_vacant(PLANTED["OP-02"])):
        pos.loc[pos["position_id"] == position_id, "org_unit_id"] = None if i % 2 == 0 else "ORG999"

    # OP-03: two active employees in the same position.
    # Move a "mover" into a "holder's" position. Same subgroup, so the
    # move does not also create an OP-05 FLSA mismatch.
    for holder in pick_emps(active["emp_id"], PLANTED["OP-03"]):
        subgroup = emp.loc[emp["emp_id"] == holder, "employee_subgroup"].iloc[0]
        mover = pick_emps(active.loc[active["employee_subgroup"] == subgroup, "emp_id"], 1)[0]
        holder_pos = emp.loc[emp["emp_id"] == holder, "position_id"].iloc[0]
        if emp_flsa(mover) != flsa_of_job[job_of_pos[holder_pos]]:
            raise RuntimeError("OP-03 plant would also create an FLSA mismatch")
        emp.loc[emp["emp_id"] == mover, "position_id"] = holder_pos
        used_positions.add(holder_pos)

    # OP-04: terminated employee still assigned to an active position.
    # The position's job matches the employee's subgroup, so this does not
    # also create an OP-05 FLSA mismatch.
    for emp_id in pick_emps(terminated["emp_id"], PLANTED["OP-04"]):
        subgroup = emp.loc[emp["emp_id"] == emp_id, "employee_subgroup"].iloc[0]
        wanted_flsa = "Exempt" if subgroup == "Salaried" else "Non-exempt"
        matching = [p for p in vacant if flsa_of_job[job_of_pos[p]] == wanted_flsa and p not in used_positions]
        position_id = rng.choice(matching)
        used_positions.add(position_id)
        emp.loc[emp["emp_id"] == emp_id, "position_id"] = position_id

    # OP-05: employee subgroup does not match the job's FLSA status.
    # 3 hourly employees marked Salaried, 2 salaried employees marked Hourly.
    for emp_id in pick_emps(active.loc[active["employee_subgroup"] == "Hourly", "emp_id"], 3):
        emp.loc[emp["emp_id"] == emp_id, "employee_subgroup"] = "Salaried"
    for emp_id in pick_emps(active.loc[active["employee_subgroup"] == "Salaried", "emp_id"], 2):
        emp.loc[emp["emp_id"] == emp_id, "employee_subgroup"] = "Hourly"

    # TP-01: paid hours differ from recorded hours by more than 0.5.
    # Change the paid regular hours; time entries stay as recorded.
    deltas = [4.0, -8.0, 1.5, -2.0, 8.0, -1.0, 3.0, -4.0]
    for emp_id, delta in zip(pick_emps(active["emp_id"], PLANTED["TP-01"]), deltas):
        adjust_pay(emp_id, pick_period(), "1000", delta)

    # TP-02: overtime paid to an exempt employee. The overtime is also
    # recorded in time entries, so paid and recorded hours still agree.
    exempt_emps = [e for e in active["emp_id"] if emp_flsa(e) == "Exempt"]
    for emp_id in pick_emps(exempt_emps, PLANTED["TP-02"]):
        period_id = pick_period()
        start, _, pay_date = period_dates(period_id)
        pay = t["payroll_results"]
        regular = pay[(pay["emp_id"] == emp_id) & (pay["period_id"] == period_id) & (pay["wage_type"] == "1000")].iloc[0]
        rate = regular["amount"] / regular["hours"]
        _append(t, "time_entries", [(emp_id, start + timedelta(days=1), 4.0, "Overtime")])
        _append(t, "payroll_results", [(period_id, emp_id, "1100", 4.0,
                                        round(4.0 * rate * OVERTIME_MULTIPLIER, 2), pay_date)])

    # TP-03: active hourly employee paid with no time entries in the period.
    # Delete one period of time entries; the payroll stays.
    hourly = active.loc[active["employee_subgroup"] == "Hourly", "emp_id"]
    for emp_id in pick_emps(hourly, PLANTED["TP-03"]):
        start, end, _ = period_dates(pick_period())
        te = t["time_entries"]
        drop = (te["emp_id"] == emp_id) & (te["work_date"] >= start) & (te["work_date"] <= end)
        t["time_entries"] = te[~drop]

    # TP-04: daily hours over 16 or negative. Payroll paid the bad hours
    # as recorded, so this does not also show up as a TP-01 variance.
    bad_hours = [18.0, 20.0, 24.0, -4.0, -8.0, -2.0]
    for emp_id, new_hours in zip(pick_emps(active["emp_id"], PLANTED["TP-04"]), bad_hours):
        te = t["time_entries"]
        idx = rng.choice(list(te.index[(te["emp_id"] == emp_id) & (te["attendance_type"] == "Regular")]))
        work_date = te.at[idx, "work_date"]
        period_id = periods.loc[(periods["start_date"] <= work_date) & (periods["end_date"] >= work_date),
                                "period_id"].iloc[0]
        adjust_pay(emp_id, period_id, "1000", new_hours - te.at[idx, "hours"])
        te.at[idx, "hours"] = new_hours

    # TP-05: duplicate payroll line (same employee, period, wage type).
    # 2 exact duplicates of a shift differential line, and 2 regular-pay
    # lines split into two halves (total hours unchanged).
    pay = t["payroll_results"]
    shift_emps = pay.loc[pay["wage_type"] == "1400", "emp_id"]
    for emp_id in pick_emps(shift_emps, 2):
        line = pay[(pay["emp_id"] == emp_id) & (pay["wage_type"] == "1400")].iloc[0]
        _append(t, "payroll_results", [tuple(line)])
    for emp_id in pick_emps(active["emp_id"], 2):
        pay = t["payroll_results"]
        idx = pay.index[(pay["emp_id"] == emp_id) & (pay["period_id"] == pick_period()) & (pay["wage_type"] == "1000")][0]
        half_hours, half_amount = pay.at[idx, "hours"] / 2, round(pay.at[idx, "amount"] / 2, 2)
        pay.at[idx, "hours"], pay.at[idx, "amount"] = half_hours, half_amount
        _append(t, "payroll_results", [tuple(pay.loc[idx])])

    # TP-06: payment dated after the employee's term date.
    # A regular-pay line for someone terminated last year.
    for emp_id in pick_emps(terminated["emp_id"], PLANTED["TP-06"]):
        period_id = pick_period()
        _, _, pay_date = period_dates(period_id)
        _append(t, "payroll_results", [(period_id, emp_id, "1000", 40.0, 800.00, pay_date)])

    return {name: _tidy(name, df) for name, df in t.items()}


# --- Helpers ----------------------------------------------------------------

SORT_KEYS = {
    "org_units": ["org_unit_id"], "jobs": ["job_id"], "positions": ["position_id"],
    "employees": ["emp_id"], "wage_types": ["wage_type"], "pay_periods": ["period_id"],
    "time_entries": ["emp_id", "work_date", "attendance_type"],
    "payroll_results": ["period_id", "emp_id", "wage_type"],
}


def _append(tables, name, rows):
    new = pd.DataFrame(rows, columns=list(SCHEMA[name]))
    tables[name] = pd.concat([tables[name], coerce(new, name)], ignore_index=True)


def _tidy(name, df):
    """Apply the schema types and a stable sort order."""
    return coerce(df, name).sort_values(SORT_KEYS[name], kind="stable").reset_index(drop=True)


def save(tables: dict[str, pd.DataFrame], data_dir: Path = DATA_DIR) -> None:
    for name, df in tables.items():
        df.to_csv(data_dir / f"{name}.csv", index=False, lineterminator="\n")
    planted = pd.DataFrame(list(PLANTED.items()), columns=["rule_id", "expected_count"])
    planted.to_csv(data_dir / "planted_defects.csv", index=False, lineterminator="\n")


def main():
    tables = plant_defects(generate_clean())
    save(tables)
    for name, df in tables.items():
        print(f"{name:16s} {len(df):6d} rows")
    print(f"planted defects  {sum(PLANTED.values()):6d} across {len(PLANTED)} rules")


if __name__ == "__main__":
    main()
