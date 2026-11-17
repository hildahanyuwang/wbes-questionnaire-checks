# What this data is, and what it is not

`synthetic_responses.csv` holds **12 synthetic interview records**. They were written by
hand so that each rule in `checks/rules.py` has at least one case to catch, and several
records carry more than one planted error.

**No World Bank Enterprise Surveys data was used.** Not the public indicators, not the
microdata, not any country dataset. Enterprise Surveys microdata is released under a
data access protocol that treats it as strictly confidential.

What *was* used is the **public core questionnaire** — the variable names (`b2a`, `d3a`,
`l1` …), the response codes, the missing-value codes and the printed skip instructions,
published on the Enterprise Surveys methodology page.

## What is planted where

| Record | Planted |
|---|---|
| SYN-001 | zeros recorded after the D.3 skip |
| SYN-002 | sole proprietorship with `b3` ≠ 100 |
| SYN-003 | sales percentages that do not total 100; registration year before start of operations |
| SYN-004 | wholly state-owned but the record continues; large fall in employment |
| SYN-005 | sole proprietorship with `b3` ≠ 100 and `b4a` ≠ 100; zeros after the D.3 skip |
| SYN-006 | a percentage outside 0–100 |
| SYN-007 | ownership percentages that do not total 100 |
| SYN-008 | never registered (`-7`) but the record continues |
| SYN-009 | a year that is not four digits |
| SYN-010 | implausible length of manager experience |
| SYN-011 | a clean "don't know" record — should produce no findings |
| SYN-012 | outage duration recorded although `c7 = 0`; tenfold employment change |

SYN-011 is there on purpose: a record where the respondent answered `-9` throughout is
*not* an error, and a check that flags it would be wrong.
