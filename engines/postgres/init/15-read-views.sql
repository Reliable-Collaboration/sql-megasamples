-- Employees' ported helper functions mirror MySQL session variables through
-- set_config. Reading these views must neither call those helpers nor acquire
-- their ability to change session state. Keep the writer's routines unchanged.
SELECT current_database() = 'employees' AS employee_database \gset
\if :employee_database
CREATE OR REPLACE VIEW public.v_full_departments (dept_no, dept_name, manager) AS
SELECT d.dept_no, d.dept_name,
       (SELECT (SELECT (e.first_name || ' ' || e.last_name)::varchar
                FROM public.employees e WHERE e.emp_no = dm.emp_no)
        FROM public.dept_manager dm
        WHERE dm.dept_no = d.dept_no
          AND dm.from_date = (SELECT max(latest.from_date) FROM public.dept_manager latest
                              WHERE latest.dept_no = d.dept_no)
        LIMIT 1) AS manager
FROM public.departments d;

CREATE OR REPLACE VIEW public.v_full_employees
    (emp_no, first_name, last_name, birth_date, gender, hire_date, department) AS
SELECT e.emp_no, e.first_name, e.last_name, e.birth_date, e.gender, e.hire_date,
       (SELECT (d.dept_name::text)::varchar FROM public.departments d
        WHERE d.dept_no =
          (SELECT de.dept_no FROM public.dept_emp de
           WHERE de.emp_no = e.emp_no
             AND de.from_date = (SELECT max(latest.from_date) FROM public.dept_emp latest
                                 WHERE latest.emp_no = e.emp_no)
           LIMIT 1)) AS department
FROM public.employees e;
\endif
