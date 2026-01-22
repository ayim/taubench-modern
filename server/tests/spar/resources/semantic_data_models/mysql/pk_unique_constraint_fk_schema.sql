-- Test schema for FK referencing table with both PRIMARY KEY and UNIQUE CONSTRAINT
-- This tests detection of FKs that reference a UNIQUE CONSTRAINT (not the PK)
-- when the parent table has both a PK and a separate UNIQUE CONSTRAINT

-- Parent table with PRIMARY KEY and separate UNIQUE CONSTRAINT
CREATE TABLE departments (
  dept_id INT NOT NULL,
  dept_code VARCHAR(10) NOT NULL,
  region_code VARCHAR(10) NOT NULL,
  dept_name VARCHAR(100) NOT NULL,
  PRIMARY KEY (dept_id),
  UNIQUE (dept_code, region_code)
) ENGINE = InnoDB;

-- Child table with FK referencing the UNIQUE CONSTRAINT (not the PK)
CREATE TABLE employees (
  id INT AUTO_INCREMENT PRIMARY KEY,
  employee_name VARCHAR(100) NOT NULL,
  dept_code VARCHAR(10) NOT NULL,
  region_code VARCHAR(10) NOT NULL,
  CONSTRAINT fk_employees_dept FOREIGN KEY (dept_code, region_code)
    REFERENCES departments(dept_code, region_code)
) ENGINE = InnoDB;
