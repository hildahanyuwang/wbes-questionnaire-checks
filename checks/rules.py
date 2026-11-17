"""Validation rules for World Bank Enterprise Surveys core questionnaire responses.

Every rule records where it comes from:

    "questionnaire"   the rule is printed on the public core questionnaire itself
                      (ES-Services.pdf, enterprisesurveys.org/methodology) and the
                      printed wording is quoted verbatim in `source_text`.
    "analyst"         the rule is not printed on the questionnaire. It is a
                      reviewer-defined consistency or plausibility check, and is
                      flagged for human review rather than treated as an error.

Missing-value codes used by the questionnaire, as printed next to the questions:

    -9  DON'T KNOW (SPONTANEOUS)
    -8  REFUSAL (SPONTANEOUS)
    -7  does not apply  (e.g. "IF ESTABLISHMENT WAS NOT IN BUSINESS IN ... -7",
                               "NEVER REGISTERED (SPONTANEOUS) -7")
    -6  STILL IN PROCESS
    -5  APPLICATION DENIED
"""

DK, REFUSAL, NOT_APPLICABLE, IN_PROCESS, DENIED = -9, -8, -7, -6, -5
MISSING_CODES = {DK, REFUSAL, NOT_APPLICABLE, IN_PROCESS, DENIED}

# Percentage questions and the missing codes each one is allowed to carry.
PERCENT_QUESTIONS = {
    "b2a": ("B.2", {DK}),
    "b2b": ("B.2", {DK}),
    "b2c": ("B.2", {DK}),
    "b2d": ("B.2", {DK}),
    "b3": ("B.3", {DK}),
    "b4a": ("B.4a", {DK}),
    "c11": ("C.11", {DK}),
    "d3a": ("D.3", {DK}),
    "d3b": ("D.3", {DK}),
    "d3c": ("D.3", {DK}),
}

# question label -> the variables it covers, for the review table
QUESTION_OF = {
    "b1": "B.1", "b2a": "B.2", "b2b": "B.2", "b2c": "B.2", "b2d": "B.2",
    "b3": "B.3", "b3a": "B.3a", "b4": "B.4", "b4a": "B.4a", "b5": "B.5",
    "b6": "B.6", "b6b": "B.6b", "b7": "B.7", "b7a": "B.7a", "b8": "B.8",
    "b8x": "B.8x", "c3": "C.3", "c4": "C.4", "c5": "C.5", "c6": "C.6",
    "c7": "C.7", "c8a": "C.8", "c8b": "C.8", "c9a": "C.9", "c9b": "C.9",
    "c10": "C.10", "c11": "C.11", "d3a": "D.3", "d3b": "D.3", "d3c": "D.3",
    "l1": "L.1", "l2": "L.2",
}


def blank(v):
    return v is None or v == ""


def answered(v):
    """An answer is present and is not one of the documented missing codes."""
    return not blank(v) and v not in MISSING_CODES


class Finding:
    __slots__ = ("record_id", "question", "variable", "value", "rule_id",
                 "rule_source", "severity", "message", "source_text")

    def __init__(self, record_id, variable, rule_id, rule_source, severity,
                 message, source_text, value=None):
        self.record_id = record_id
        self.variable = variable
        self.question = QUESTION_OF.get(variable, "")
        self.value = "" if value is None else value
        self.rule_id = rule_id
        self.rule_source = rule_source
        self.severity = severity
        self.message = message
        self.source_text = source_text


# --------------------------------------------------------------------------
# 1. Permitted values
# --------------------------------------------------------------------------

def r01_percent_range(rec, out):
    """Percentages must be 0-100, or a missing code the question actually offers."""
    for var, (_q, allowed) in PERCENT_QUESTIONS.items():
        v = rec.get(var)
        if blank(v):
            continue
        if v in MISSING_CODES:
            if v not in allowed:
                out.append(Finding(
                    rec["id"], var, "R01b", "questionnaire", "error",
                    f"missing code {v} is not offered for this question "
                    f"(offered: {sorted(allowed)})",
                    "Codes printed next to the question", value=v))
            continue
        if not (0 <= v <= 100):
            out.append(Finding(
                rec["id"], var, "R01", "questionnaire", "error",
                "percentage outside the permitted 0-100 range",
                "Question is answered in 'Percent'", value=v))


def r02_coded_answer_values(rec, out):
    """Yes/No questions must carry 1, 2 or a documented missing code."""
    for var, allowed in (("b3a", {1, 2, DK}), ("b4", {1, 2, DK}),
                         ("b7a", {1, 2, DK}), ("b8", {1, 2, IN_PROCESS, DK}),
                         ("c3", {1, 2, DK}), ("c5", {1, 2, DK, REFUSAL}),
                         ("c6", {1, 2, DK}), ("c10", {1, 2, DK})):
        v = rec.get(var)
        if blank(v) or v in allowed:
            continue
        out.append(Finding(
            rec["id"], var, "R02", "questionnaire", "error",
            f"value is not one of the printed response codes {sorted(allowed)}",
            "Response codes printed next to the question", value=v))


# --------------------------------------------------------------------------
# 2. Percentages that must total 100
# --------------------------------------------------------------------------

_SUM_TEXT = ("INTERVIEWER: CHECK THAT TOTAL SUMS TO 100% "
             "UNLESS RESPONDENT DOES NOT KNOW")


def _check_sum(rec, out, vars_, rule_id, anchor):
    values = [rec.get(v) for v in vars_]
    if any(blank(v) for v in values):
        return
    if any(v == DK for v in values):
        return  # the printed instruction exempts "does not know"
    total = sum(values)
    if total != 100:
        out.append(Finding(
            rec["id"], anchor, rule_id, "questionnaire", "error",
            f"{'+'.join(vars_)} = {total}, does not total 100",
            _SUM_TEXT, value=total))


def r03_ownership_sums_to_100(rec, out):
    _check_sum(rec, out, ["b2a", "b2b", "b2c", "b2d"], "R03", "b2a")


def r04_sales_sums_to_100(rec, out):
    _check_sum(rec, out, ["d3a", "d3b", "d3c"], "R04", "d3a")


# --------------------------------------------------------------------------
# 3. Skip patterns printed on the questionnaire
# --------------------------------------------------------------------------

def _check_skip(rec, out, cond, skipped_vars, rule_id, source_text, anchor):
    """A question that the skip pattern should have passed over carries an answer.

    A recorded zero is treated differently from a recorded quantity. Fieldwork
    software and keyers often write 0 into a skipped numeric field, which is
    inconsistent with the printed skip but does not change what the record says.
    A non-zero answer after a skip does change it, and is the one that has to go
    back to the contractor.
    """
    if not cond:
        return
    whence = QUESTION_OF.get(anchor, anchor)
    for var in skipped_vars:
        v = rec.get(var)
        if blank(v):
            continue
        if v == 0:
            out.append(Finding(
                rec["id"], var, rule_id + "z", "questionnaire", "review",
                f"zero recorded although the skip from {whence} should have passed "
                "over this question; confirm whether it was asked or auto-filled",
                source_text, value=v))
        else:
            out.append(Finding(
                rec["id"], var, rule_id, "questionnaire", "error",
                f"answered although the skip from {whence} should have passed over it",
                source_text, value=v))


def r05_skip_quality_certification(rec, out):
    _check_skip(rec, out, rec.get("b8") in (2, DK), ["b8x"], "R05",
                "B.8  No 2 GO TO C.3 / DON'T KNOW -9 GO TO C.3", "b8")


def r06_skip_female_ownership(rec, out):
    _check_skip(rec, out, rec.get("b4") in (2, DK), ["b4a"], "R06",
                "B.4  No 2 GO TO B.5 / DON'T KNOW -9 GO TO B.5", "b4")


def r07_skip_electrical_connection(rec, out):
    _check_skip(rec, out, rec.get("c3") in (2, DK), ["c4", "c5"], "R07",
                "C.3  No 2 GO TO C.6 / DON'T KNOW -9 GO TO C.6", "c3")


def r08_skip_power_outages(rec, out):
    _check_skip(rec, out, rec.get("c6") in (2, DK),
                ["c7", "c8a", "c8b", "c9a", "c9b"], "R08",
                "C.6  No 2 GO TO C.10 / DON'T KNOW -9 GO TO C.10", "c6")


def r09_skip_outage_duration(rec, out):
    _check_skip(rec, out, rec.get("c7") == 0, ["c8a", "c8b"], "R09",
                "C.7  IF 0, GO TO C.9", "c7")


def r10_skip_generator(rec, out):
    _check_skip(rec, out, rec.get("c10") in (2, DK), ["c11"], "R10",
                "C.10  No 2 GO TO C.12 / DON'T KNOW -9 GO TO C.12", "c10")


def r11_skip_exports(rec, out):
    _check_skip(rec, out, rec.get("d3a") == 100, ["d3b", "d3c"], "R11",
                "D.3  National sales d3a % -9 IF 100% GO TO D.10", "d3a")


# --------------------------------------------------------------------------
# 4. Consistency rules printed as interviewer notes
# --------------------------------------------------------------------------

def r12_sole_proprietor_largest_owner(rec, out):
    if rec.get("b1") == 3 and answered(rec.get("b3")) and rec.get("b3") != 100:
        out.append(Finding(
            rec["id"], "b3", "R12", "questionnaire", "error",
            "b1 = 3 (sole proprietorship) but b3 is not 100",
            "INTERVIEWER: PLEASE NOTE WHEN b1 IS 3 (SOLE PROPRIETORSHIP), "
            "ENTER 100% FOR QUESTION b3.", value=rec.get("b3")))


def r13_sole_proprietor_female_owner(rec, out):
    if (rec.get("b1") == 3 and rec.get("b4") == 1
            and answered(rec.get("b4a")) and rec.get("b4a") != 100):
        out.append(Finding(
            rec["id"], "b4a", "R13", "questionnaire", "error",
            "b1 = 3 and b4 = 1 but b4a is not 100",
            "INTERVIEWER: PLEASE NOTE WHEN b1 IS 3 (SOLE PROPRIETORSHIP) and b4 is 1 "
            "(FIRM HAS A FEMALE OWNER), ENTER 100% FOR QUESTION b4a.",
            value=rec.get("b4a")))


def r14_state_owned_should_terminate(rec, out):
    if rec.get("b2c") == 100:
        out.append(Finding(
            rec["id"], "b2c", "R14", "questionnaire", "error",
            "b2c = 100 (wholly government owned) but the record continues; "
            "the interview should have ended here",
            "B.2  Government or State b2c % -9 IF 100% END INTERVIEW", value=100))


def r15_never_registered_should_terminate(rec, out):
    if rec.get("b6b") == NOT_APPLICABLE:
        out.append(Finding(
            rec["id"], "b6b", "R15", "questionnaire", "error",
            "b6b = -7 (never registered) but the record continues; "
            "the interview should have terminated",
            "B.6b  NEVER REGISTERED (SPONTANEOUS) -7 TERMINATE", value=NOT_APPLICABLE))


def r16_year_is_four_digits(rec, out):
    for var in ("b5", "b6b"):
        v = rec.get(var)
        if blank(v) or v in MISSING_CODES:
            continue
        if not (1000 <= v <= 9999):
            out.append(Finding(
                rec["id"], var, "R16", "questionnaire", "error",
                "year is not written as four digits",
                "INTERVIEWER: PROVIDE FOUR DIGITS FOR YEAR", value=v))


# --------------------------------------------------------------------------
# 5. Reviewer-defined checks. Not printed on the questionnaire.
#    These are raised for human review, never auto-corrected.
# --------------------------------------------------------------------------

def r20_registered_before_operating(rec, out):
    b5, b6b = rec.get("b5"), rec.get("b6b")
    if answered(b5) and answered(b6b) and b6b < b5:
        out.append(Finding(
            rec["id"], "b6b", "R20", "analyst", "review",
            f"formal registration ({b6b}) precedes the start of operations ({b5}); "
            "possible but worth confirming with the respondent",
            "Not printed on the questionnaire; reviewer-defined consistency check",
            value=b6b))


def r21_startup_exceeds_current_employment(rec, out):
    b6, l1 = rec.get("b6"), rec.get("l1")
    if answered(b6) and answered(l1) and b6 > 5 * max(l1, 1):
        out.append(Finding(
            rec["id"], "b6", "R21", "analyst", "review",
            f"start-up workforce ({b6}) is more than five times current permanent "
            f"full-time employment ({l1})",
            "Not printed on the questionnaire; reviewer-defined plausibility check",
            value=b6))


def r22_employment_jump(rec, out):
    l1, l2 = rec.get("l1"), rec.get("l2")
    if answered(l1) and answered(l2) and l2 > 0 and (l1 / l2 > 10 or l1 / l2 < 0.1):
        out.append(Finding(
            rec["id"], "l1", "R22", "analyst", "review",
            f"permanent full-time employment moved from {l2} to {l1} over two fiscal "
            "years, a tenfold change or more",
            "Not printed on the questionnaire; reviewer-defined plausibility check",
            value=l1))


def r23_manager_experience_exceeds_age(rec, out):
    b7, b5 = rec.get("b7"), rec.get("b5")
    if answered(b7) and answered(b5) and b7 > 70:
        out.append(Finding(
            rec["id"], "b7", "R23", "analyst", "review",
            f"top manager's sector experience ({b7} years) is implausibly long",
            "Not printed on the questionnaire; reviewer-defined plausibility check",
            value=b7))


ALL_RULES = [
    r01_percent_range, r02_coded_answer_values,
    r03_ownership_sums_to_100, r04_sales_sums_to_100,
    r05_skip_quality_certification, r06_skip_female_ownership,
    r07_skip_electrical_connection, r08_skip_power_outages,
    r09_skip_outage_duration, r10_skip_generator, r11_skip_exports,
    r12_sole_proprietor_largest_owner, r13_sole_proprietor_female_owner,
    r14_state_owned_should_terminate, r15_never_registered_should_terminate,
    r16_year_is_four_digits,
    r20_registered_before_operating, r21_startup_exceeds_current_employment,
    r22_employment_jump, r23_manager_experience_exceeds_age,
]


def run_all(records):
    findings = []
    for rec in records:
        for rule in ALL_RULES:
            rule(rec, findings)
    findings.sort(key=lambda f: (str(f.record_id), f.question, f.rule_id))
    return findings
