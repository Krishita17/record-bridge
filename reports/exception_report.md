# RecordBridge Exception Report

- **Total exceptions:** 390 (390 errors, 0 warnings)
- **Distinct rows affected:** 390

## Breakdown by field

| field      | severity   |   count |
|:-----------|:-----------|--------:|
| dob        | error      |     129 |
| email      | error      |      79 |
| first_name | error      |      14 |
| gpa        | error      |      73 |
| last_name  | error      |      16 |
| student_id | error      |      79 |

## Sample exceptions (first 25)

|   row_index | field      | severity   | rule_violated                  |
|------------:|:-----------|:-----------|:-------------------------------|
|         250 | dob        | error      | date: date is in the future    |
|         436 | dob        | error      | date: unparseable date         |
|        3884 | dob        | error      | date: date is in the future    |
|        4554 | student_id | error      | regex: does not match ^S\d{7}$ |
|        4807 | dob        | error      | required: value is blank       |
|        3484 | dob        | error      | date: unparseable date         |
|        4906 | first_name | error      | required: value is blank       |
|        2695 | student_id | error      | regex: does not match ^S\d{7}$ |
|        2738 | dob        | error      | date: date is in the future    |
|        1854 | gpa        | error      | range: above maximum 4.0       |
|        4403 | student_id | error      | regex: does not match ^S\d{7}$ |
|        2433 | gpa        | error      | range: above maximum 4.0       |
|        4407 | email      | error      | email: malformed email         |
|        3486 | email      | error      | required: value is blank       |
|        3440 | student_id | error      | regex: does not match ^S\d{7}$ |
|        1680 | email      | error      | email: malformed email         |
|        2269 | last_name  | error      | required: value is blank       |
|        4067 | dob        | error      | required: value is blank       |
|        1505 | dob        | error      | date: date is in the future    |
|         885 | first_name | error      | required: value is blank       |
|         747 | student_id | error      | regex: does not match ^S\d{7}$ |
|        4140 | dob        | error      | required: value is blank       |
|        1849 | dob        | error      | date: date is in the future    |
|        1944 | email      | error      | email: malformed email         |
|        3831 | dob        | error      | required: value is blank       |
