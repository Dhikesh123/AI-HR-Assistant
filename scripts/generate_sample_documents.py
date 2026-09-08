"""Generate the fictional sample HR documents used by the demo.

Every document is invented for ACME Corporation. No real company policy and no
real employee data is used anywhere in this project.

Run with:  python -m scripts.generate_sample_documents
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "data" / "sample_hr_documents"
COMPANY = "ACME Corporation"

# Each document is: filename -> (subtitle, [(section title, [paragraphs/bullets])])
# One section renders per page, so page numbers in citations are stable.
Section = Tuple[str, List[str]]

DOCUMENTS: Dict[str, Tuple[str, List[Section]]] = {
    "leave_policy.pdf": (
        "Leave Policy - HR-POL-004 - Effective 01 January 2025",
        [
            (
                "1. Purpose and Scope",
                [
                    "This Leave Policy defines the paid and unpaid leave available to all "
                    "confirmed and probationary employees of ACME Corporation across its "
                    "India and APAC offices.",
                    "The policy applies to full-time employees. Contractors and interns are "
                    "covered by separate engagement terms agreed with the HR Business Partner.",
                    "The People Operations team owns this policy and reviews it annually. "
                    "Any exception requires written approval from the Head of Human Resources.",
                ],
            ),
            (
                "2. Definitions",
                [
                    "Leave Year: the calendar year running from 1 January to 31 December.",
                    "Casual Leave: short-notice paid leave for personal errands and unplanned "
                    "commitments of one or two days.",
                    "Earned Leave: paid leave accrued monthly and intended for planned "
                    "vacations of three or more days.",
                    "Sick Leave: paid leave taken for the employee's own illness, medical "
                    "appointments, or recovery from a medical procedure.",
                    "Working Day: any day that is not a weekend or a declared company holiday.",
                ],
            ),
            (
                "3. Eligibility and Accrual",
                [
                    "Employees become eligible for all leave categories from their date of "
                    "joining. Leave is credited on a pro-rata basis in the year of joining, "
                    "calculated from the joining month.",
                    "Earned leave accrues at 1.5 days per completed calendar month of service "
                    "and is credited to the employee's balance on the first day of the "
                    "following month.",
                    "Casual leave and sick leave are credited in full at the start of the leave "
                    "year and are not accrued monthly.",
                    "Employees serving a notice period may not take earned leave without the "
                    "written approval of their reporting manager and the HR Business Partner.",
                ],
            ),
            (
                "4. Leave Entitlement",
                [
                    "Every confirmed employee is entitled to 12 casual leaves per leave year. "
                    "Casual leave may be taken for a maximum of two consecutive working days at "
                    "a time.",
                    "Every confirmed employee is entitled to 15 sick leaves per leave year. A "
                    "medical certificate is required for any sick leave of three or more "
                    "consecutive working days.",
                    "Every confirmed employee is entitled to 18 earned leaves per leave year, "
                    "accrued at 1.5 days per month.",
                    "In total, an employee receives 45 days of paid leave per leave year, "
                    "excluding public holidays and any special leave described in section 7.",
                    "Leave balances are visible to employees at any time in the ACME HR portal "
                    "under My Leave, and are updated within one working day of approval.",
                ],
            ),
            (
                "5. Carry Forward and Encashment",
                [
                    "A maximum of 10 unused earned leaves may be carried forward into the next "
                    "leave year. Any earned leave above that limit lapses on 31 December.",
                    "Casual leave cannot be carried forward. Unused casual leave lapses at the "
                    "end of the leave year in which it was credited.",
                    "Sick leave cannot be carried forward and cannot be encashed under any "
                    "circumstances.",
                    "Employees may encash up to 15 earned leaves at the time of resignation or "
                    "retirement. Encashment is calculated on basic salary and is processed with "
                    "the final settlement.",
                ],
            ),
            (
                "6. Applying for Leave",
                [
                    "All leave must be applied for through the ACME HR portal. Email or verbal "
                    "requests are not treated as valid leave applications.",
                    "Planned leave of three or more days must be applied for at least seven "
                    "calendar days in advance so that work can be handed over.",
                    "Casual leave should be applied for at least one working day in advance "
                    "wherever the reason is foreseeable.",
                    "Sick leave may be applied for retrospectively, but the employee must inform "
                    "their reporting manager before 10:00 AM on the first day of absence.",
                    "Reporting managers are expected to approve or reject a leave request within "
                    "two working days. Unactioned requests escalate automatically to the "
                    "skip-level manager.",
                ],
            ),
            (
                "7. Special Leave",
                [
                    "Maternity leave of 26 weeks of paid leave is available to eligible female "
                    "employees for the first two children, and 12 weeks thereafter.",
                    "Paternity leave of 10 working days of paid leave may be taken within six "
                    "months of the date of birth or adoption.",
                    "Bereavement leave of five working days of paid leave is available on the "
                    "death of an immediate family member.",
                    "Marriage leave of five working days of paid leave is available once during "
                    "an employee's tenure at ACME Corporation.",
                    "Special leave does not reduce the casual, sick or earned leave balance.",
                ],
            ),
            (
                "8. Leave Without Pay",
                [
                    "Leave without pay is granted only when all paid leave balances have been "
                    "exhausted, and requires approval from both the reporting manager and the "
                    "Head of Human Resources.",
                    "A continuous period of leave without pay may not exceed 30 calendar days "
                    "in a leave year without an approved sabbatical agreement.",
                    "Absence of three or more consecutive working days without an approved leave "
                    "application is treated as unauthorised absence and is handled under the "
                    "Attendance Policy.",
                ],
            ),
        ],
    ),
    "work_from_home_policy.pdf": (
        "Work From Home and Hybrid Work Policy - HR-POL-007 - Effective 01 March 2025",
        [
            (
                "1. Purpose",
                [
                    "ACME Corporation operates a hybrid working model that balances the "
                    "flexibility employees value with the in-person collaboration teams need.",
                    "This policy sets out how often employees may work remotely, how remote days "
                    "are requested, and the standards expected while working from home.",
                ],
            ),
            (
                "2. Hybrid Work Entitlement",
                [
                    "Employees may work from home up to 2 days per week. The remaining three "
                    "days are worked from the assigned ACME office.",
                    "Teams designate Tuesday and Thursday as anchor days on which the whole team "
                    "is expected in the office. Work from home days are therefore normally taken "
                    "on Monday, Wednesday or Friday.",
                    "Remote days do not carry forward. An unused work from home day in one week "
                    "cannot be added to the following week.",
                    "Employees in their first 60 days of employment work from the office five "
                    "days a week to support onboarding, unless the HR Business Partner approves "
                    "an exception.",
                ],
            ),
            (
                "3. Requesting Remote Work",
                [
                    "Regular work from home days are recorded in the ACME HR portal under My "
                    "Work Location by Friday of the preceding week.",
                    "Ad-hoc remote work for reasons such as a home repair or a medical "
                    "appointment requires informing the reporting manager by message before the "
                    "start of the working day.",
                    "Requests to work remotely for more than 10 consecutive working days are "
                    "treated as extended remote work and need approval from the department head.",
                ],
            ),
            (
                "4. Eligibility and Exceptions",
                [
                    "Roles that require physical presence, including facilities, reception, lab "
                    "operations and hardware support, are not eligible for the standard hybrid "
                    "entitlement.",
                    "Employees with a documented medical condition or accessibility requirement "
                    "may request a permanent remote arrangement through the HR Business Partner.",
                    "Employees on a performance improvement plan work from the office full time "
                    "for the duration of the plan.",
                ],
            ),
            (
                "5. Expectations While Working Remotely",
                [
                    "Employees must be reachable on the approved collaboration tools during core "
                    "hours of 10:00 AM to 5:00 PM.",
                    "A stable internet connection of at least 25 Mbps is expected. ACME provides "
                    "a monthly internet allowance of INR 1,000 to employees on the hybrid model.",
                    "Company data may only be accessed from an ACME-issued device connected to "
                    "the corporate VPN. Working from public or unsecured networks without the "
                    "VPN is prohibited.",
                    "Employees are responsible for a safe and ergonomic home workspace. ACME "
                    "offers a one-time home office setup reimbursement of INR 15,000.",
                ],
            ),
            (
                "6. Working From a Different City",
                [
                    "Employees who wish to work from a city other than their base location for "
                    "more than 15 working days must obtain written approval from their "
                    "department head and notify HR, as this can have payroll and tax "
                    "implications.",
                    "Working from outside the country requires prior approval from the Head of "
                    "Human Resources and the Finance team, and is normally limited to 30 days "
                    "per leave year.",
                ],
            ),
        ],
    ),
    "attendance_policy.pdf": (
        "Attendance and Working Hours Policy - HR-POL-002 - Effective 01 January 2025",
        [
            (
                "1. Working Hours",
                [
                    "The standard working week at ACME Corporation is 40 hours, worked across "
                    "five days from Monday to Friday.",
                    "The standard working day is 9 hours including a one-hour lunch break, "
                    "typically from 9:30 AM to 6:30 PM.",
                    "Core hours during which every employee is expected to be available are "
                    "10:00 AM to 5:00 PM.",
                    "Employees may shift their start time between 8:00 AM and 10:30 AM with the "
                    "agreement of their reporting manager, provided core hours are covered.",
                ],
            ),
            (
                "2. Attendance Recording",
                [
                    "Attendance is recorded automatically through office access card swipes and "
                    "through VPN sign-in on work from home days.",
                    "Employees must record a minimum of 8 working hours per day and an average "
                    "of 40 hours per week.",
                    "Attendance regularisation for a missed swipe must be submitted in the ACME "
                    "HR portal within five working days of the affected date.",
                ],
            ),
            (
                "3. Late Arrival and Early Departure",
                [
                    "Arrival after 10:30 AM without prior information to the reporting manager is "
                    "recorded as a late arrival.",
                    "Three late arrivals in a calendar month result in a deduction of half a day "
                    "of casual leave.",
                    "Leaving before 5:00 PM without approval is recorded as an early departure "
                    "and is treated in the same way as a late arrival.",
                ],
            ),
            (
                "4. Unauthorised Absence",
                [
                    "Absence without an approved leave application or intimation to the "
                    "reporting manager is treated as unauthorised absence and is unpaid.",
                    "Three or more consecutive days of unauthorised absence trigger a formal "
                    "notice from Human Resources.",
                    "Continued unauthorised absence beyond eight consecutive working days may be "
                    "treated as voluntary abandonment of employment.",
                ],
            ),
            (
                "5. Overtime and Compensatory Off",
                [
                    "Employees required to work on a declared holiday or a weekend at the "
                    "request of their manager are eligible for a compensatory off.",
                    "Compensatory off must be availed within 30 calendar days of the day worked, "
                    "after which it lapses.",
                    "Compensatory off is not encashable and does not add to the earned leave "
                    "balance.",
                ],
            ),
        ],
    ),
    "holiday_policy.pdf": (
        "Holiday Policy and Holiday Calendar 2025 - HR-POL-005",
        [
            (
                "1. Holiday Entitlement",
                [
                    "ACME Corporation observes 12 paid public holidays in each calendar year for "
                    "its India offices.",
                    "Of these, 10 holidays are fixed for all employees and 2 are optional "
                    "restricted holidays that each employee selects according to personal "
                    "preference.",
                    "The holiday calendar is published by Human Resources in December for the "
                    "following calendar year.",
                ],
            ),
            (
                "2. Fixed Holidays 2025",
                [
                    "New Year's Day - 1 January 2025",
                    "Republic Day - 26 January 2025",
                    "Holi - 14 March 2025",
                    "Good Friday - 18 April 2025",
                    "Labour Day - 1 May 2025",
                    "Independence Day - 15 August 2025",
                    "Gandhi Jayanti - 2 October 2025",
                    "Dussehra - 2 October 2025",
                    "Diwali - 20 October 2025",
                    "Christmas Day - 25 December 2025",
                ],
            ),
            (
                "3. Restricted Holidays",
                [
                    "Each employee may select 2 restricted holidays per calendar year from the "
                    "published list of 8 optional festival days.",
                    "Restricted holidays must be selected in the ACME HR portal by 31 January "
                    "and applied for at least three working days in advance.",
                    "Unused restricted holidays lapse at the end of the calendar year and cannot "
                    "be encashed or carried forward.",
                ],
            ),
            (
                "4. Holidays Falling on a Weekend",
                [
                    "A public holiday that falls on a Saturday or Sunday is not moved to another "
                    "day and no substitute holiday is granted.",
                    "Where a holiday falls on a Tuesday or Thursday, teams may agree an optional "
                    "bridge day taken from the earned leave balance.",
                ],
            ),
            (
                "5. Working on a Holiday",
                [
                    "Employees in support and operations roles may be rostered to work on a "
                    "public holiday to maintain service coverage.",
                    "Any employee who works on a public holiday receives one compensatory off, "
                    "to be availed within 30 calendar days.",
                ],
            ),
        ],
    ),
    "benefits_policy.pdf": (
        "Employee Benefits Policy - HR-POL-009 - Effective 01 April 2025",
        [
            (
                "1. Overview",
                [
                    "ACME Corporation offers a benefits programme covering health, financial "
                    "security, learning and wellbeing.",
                    "All benefits described here are available to confirmed full-time employees "
                    "from their date of joining unless stated otherwise.",
                ],
            ),
            (
                "2. Health Insurance",
                [
                    "Every employee is covered by a group medical insurance policy with a sum "
                    "insured of INR 5,00,000 per family per year.",
                    "Coverage is on a floater basis and includes the employee, spouse and up to "
                    "two dependent children from the date of joining.",
                    "Parents may be added to the policy at an additional annual premium of INR "
                    "12,000, deducted from salary in equal monthly instalments.",
                    "The policy includes pre-existing conditions from day one and covers "
                    "hospitalisation of 24 hours or more, along with listed day-care procedures.",
                    "Claims are submitted through the insurer's portal within 30 days of "
                    "discharge. The HR service desk assists with escalations.",
                ],
            ),
            (
                "3. Life and Accident Cover",
                [
                    "Group term life insurance is provided at three times the annual fixed "
                    "salary, at no cost to the employee.",
                    "Group personal accident cover is provided at two times the annual fixed "
                    "salary and applies 24 hours a day, worldwide.",
                ],
            ),
            (
                "4. Retirement Benefits",
                [
                    "Provident fund is contributed at 12 percent of basic salary by both the "
                    "employee and ACME Corporation, in line with statutory requirements.",
                    "Gratuity is payable in accordance with the Payment of Gratuity Act to "
                    "employees who complete five years of continuous service.",
                    "The National Pension System is available as an optional salary structuring "
                    "component and may be elected during the annual flexible benefits window.",
                ],
            ),
            (
                "5. Learning and Development",
                [
                    "Each employee receives an annual learning allowance of INR 25,000 for "
                    "courses, certifications, books and conference tickets.",
                    "Certification examination fees for role-relevant certifications are "
                    "reimbursed in full on first attempt, subject to manager approval before "
                    "registration.",
                    "Employees may use up to 5 working days per year as dedicated learning days.",
                ],
            ),
            (
                "6. Wellbeing Benefits",
                [
                    "An annual wellness allowance of INR 12,000 covers gym membership, sports "
                    "activities, and mental wellbeing subscriptions.",
                    "The Employee Assistance Programme offers 8 free confidential counselling "
                    "sessions per employee per year, available 24 hours a day.",
                    "An annual preventive health check-up is provided free of cost to every "
                    "employee above the age of 30.",
                ],
            ),
            (
                "7. Allowances and Reimbursements",
                [
                    "A meal allowance of INR 2,200 per month is credited to the employee's meal "
                    "card.",
                    "An internet allowance of INR 1,000 per month is paid to employees on the "
                    "hybrid work model.",
                    "A one-time home office setup reimbursement of INR 15,000 is available to "
                    "employees who work from home regularly.",
                    "Domestic travel on company business is reimbursed at actuals against bills "
                    "submitted within 30 days of travel, in line with the Travel and Expense "
                    "guidelines.",
                ],
            ),
        ],
    ),
    "employee_handbook.pdf": (
        "Employee Handbook - Edition 6 - January 2025",
        [
            (
                "1. Welcome to ACME",
                [
                    "ACME Corporation is a fictional technology company used for demonstration "
                    "purposes. It designs industrial automation software and employs about "
                    "1,800 people across four offices.",
                    "This handbook summarises the policies that shape day-to-day working life at "
                    "ACME. Where the handbook and a specific policy document differ, the "
                    "specific policy document takes precedence.",
                ],
            ),
            (
                "2. Our Values",
                [
                    "Customer obsession: we start with the customer problem and work backwards.",
                    "Craft: we take pride in the quality and clarity of what we build.",
                    "Candour: we raise concerns early, directly and respectfully.",
                    "Care: we look after each other's wellbeing as much as our results.",
                ],
            ),
            (
                "3. Employment Basics",
                [
                    "The probation period for new employees is 6 months from the date of "
                    "joining. Confirmation is subject to a satisfactory performance review.",
                    "The notice period is 30 days during probation and 60 days after "
                    "confirmation, for both the employee and the company.",
                    "Salary is credited on the last working day of each month. Payslips are "
                    "available in the ACME HR portal from the first working day of the following "
                    "month.",
                    "The performance review cycle runs twice a year, in April and October. "
                    "Annual increments are effective from 1 July.",
                ],
            ),
            (
                "4. Time Off at a Glance",
                [
                    "12 casual leaves, 15 sick leaves and 18 earned leaves are available each "
                    "leave year. Full details are in the Leave Policy.",
                    "12 paid public holidays are observed each year, of which 2 are restricted "
                    "holidays chosen by the employee.",
                    "Employees may work from home up to 2 days per week under the hybrid work "
                    "model.",
                ],
            ),
            (
                "5. Workplace Standards",
                [
                    "ACME maintains a zero tolerance position on harassment and discrimination "
                    "of any kind, as detailed in the Code of Conduct.",
                    "Company property, including laptops and access cards, must be returned on "
                    "the last working day.",
                    "Employees must not share confidential company or customer information "
                    "outside ACME, during or after employment.",
                ],
            ),
            (
                "6. Who to Contact",
                [
                    "HR service desk: raise a ticket in the ACME HR portal for any policy, "
                    "payroll or benefits question. First response is within one working day.",
                    "HR Business Partner: for confidential matters, career conversations and "
                    "policy exceptions.",
                    "Ethics helpline: for anonymous reporting of any suspected breach of the "
                    "Code of Conduct.",
                ],
            ),
        ],
    ),
    "recruitment_policy.pdf": (
        "Recruitment and Selection Policy - HR-POL-011 - Effective 01 January 2025",
        [
            (
                "1. Principles",
                [
                    "ACME Corporation recruits on merit. Selection decisions are based on "
                    "skills, experience and demonstrated potential relevant to the role.",
                    "Every open role is approved by the hiring manager, the department head and "
                    "the Finance team before it is posted.",
                    "All roles are advertised internally on the ACME careers page for five "
                    "working days before external sourcing begins.",
                ],
            ),
            (
                "2. Interview Process",
                [
                    "The standard interview process consists of four stages: a recruiter "
                    "screen, a technical or functional round, a hiring manager round, and a "
                    "values interview.",
                    "Each interview panel must include at least one interviewer from outside the "
                    "hiring team.",
                    "Interview feedback must be submitted in the applicant tracking system "
                    "within 24 hours of the interview.",
                    "The target time from application to offer decision is 21 calendar days.",
                ],
            ),
            (
                "3. Employee Referrals",
                [
                    "Employees may refer candidates for any open role through the referral "
                    "portal.",
                    "A referral bonus of INR 50,000 is paid for a successful referral at "
                    "engineering levels 3 and above, and INR 25,000 for other roles.",
                    "The referral bonus is paid after the referred employee completes 90 days of "
                    "service.",
                    "Referrals of immediate family members must be declared and are handled by an "
                    "independent panel.",
                ],
            ),
            (
                "4. Offers and Background Checks",
                [
                    "Offer letters are issued by Human Resources only. No other communication "
                    "constitutes an offer of employment.",
                    "All offers are conditional on a satisfactory background verification "
                    "covering identity, education, and previous employment.",
                    "Candidates have 7 calendar days to accept an offer, after which it may be "
                    "withdrawn.",
                ],
            ),
            (
                "5. Internal Mobility",
                [
                    "Employees become eligible to apply for an internal move after completing 12 "
                    "months in their current role.",
                    "Internal applicants must inform their current manager before the hiring "
                    "manager round.",
                    "A successful internal move takes effect after a transition period of up to "
                    "30 days agreed between both managers.",
                ],
            ),
        ],
    ),
    "joining_process.pdf": (
        "Joining and Onboarding Process - HR-PRO-001 - Effective 01 January 2025",
        [
            (
                "1. Before Day One",
                [
                    "The offer letter and appointment letter are issued through the ACME HR "
                    "portal and must be signed digitally before the joining date.",
                    "Pre-joining documents are uploaded at least five working days before day "
                    "one so that IT and payroll setup can be completed.",
                    "The IT team ships the laptop to the address confirmed by the new joiner at "
                    "least two working days before the joining date.",
                ],
            ),
            (
                "2. Documents Required",
                [
                    "Government photo identity proof and address proof.",
                    "PAN card and Aadhaar number for payroll and statutory registration.",
                    "Educational certificates for the highest qualification.",
                    "Relieving letter and experience letter from the most recent employer.",
                    "Salary slips for the last three months of previous employment.",
                    "Two passport size photographs and completed bank account details.",
                ],
            ),
            (
                "3. Day One",
                [
                    "New joiners report to the reception of their assigned office at 10:00 AM, "
                    "or join the virtual induction call for remote onboarding.",
                    "The induction session covers company introduction, policies, information "
                    "security and benefits enrolment, and runs for approximately three hours.",
                    "Access cards, email accounts and system access are issued on the first day. "
                    "Any pending access is escalated to the IT service desk.",
                ],
            ),
            (
                "4. First 90 Days",
                [
                    "Every new joiner is assigned an onboarding buddy from their team for the "
                    "first 90 days.",
                    "A structured 30-60-90 day plan is agreed with the reporting manager in the "
                    "first week.",
                    "New joiners work from the office five days a week for the first 60 days to "
                    "support onboarding and team integration.",
                    "A formal check-in with the HR Business Partner takes place at day 30 and "
                    "day 90.",
                ],
            ),
            (
                "5. Confirmation",
                [
                    "The probation period is 6 months. A confirmation review is scheduled in the "
                    "final month of probation.",
                    "Confirmation is communicated in writing by Human Resources. Probation may "
                    "be extended once by up to 3 months where performance needs improvement.",
                ],
            ),
        ],
    ),
    "code_of_conduct.pdf": (
        "Code of Conduct - HR-POL-001 - Effective 01 January 2025",
        [
            (
                "1. Our Commitment",
                [
                    "Every employee, contractor and board member of ACME Corporation is expected "
                    "to act with honesty, fairness and respect.",
                    "This Code sets the minimum standard of behaviour. Where local law is "
                    "stricter, local law applies.",
                ],
            ),
            (
                "2. Respect in the Workplace",
                [
                    "ACME does not tolerate harassment, bullying or discrimination on any "
                    "ground, including gender, religion, caste, age, disability or sexual "
                    "orientation.",
                    "An Internal Committee constituted under the Prevention of Sexual Harassment "
                    "law investigates all complaints of sexual harassment. Complaints are "
                    "acknowledged within 3 working days and inquiry is completed within 90 days.",
                    "Retaliation against anyone who raises a concern in good faith is itself a "
                    "serious breach of this Code.",
                ],
            ),
            (
                "3. Conflicts of Interest",
                [
                    "Employees must declare any outside employment, directorship, or business "
                    "interest that could conflict with their ACME responsibilities.",
                    "Employees may not participate in a hiring, procurement or appraisal decision "
                    "involving an immediate family member or close personal relation.",
                    "Gifts from vendors or customers with a value above INR 2,500 must be "
                    "declared and may not be accepted without approval.",
                ],
            ),
            (
                "4. Confidentiality and Data Protection",
                [
                    "Customer data, employee personal data and unreleased product information "
                    "are confidential and must be handled only on approved ACME systems.",
                    "Confidentiality obligations continue after employment ends.",
                    "Any suspected data breach must be reported to the security team within 24 "
                    "hours of discovery.",
                ],
            ),
            (
                "5. Raising Concerns",
                [
                    "Concerns may be raised with the reporting manager, the HR Business Partner, "
                    "or anonymously through the ethics helpline.",
                    "All reports are handled confidentially and investigated impartially.",
                    "Breaches of this Code may lead to disciplinary action up to and including "
                    "termination of employment.",
                ],
            ),
        ],
    ),
    "hr_faq.pdf": (
        "HR Frequently Asked Questions - Updated January 2025",
        [
            (
                "1. Leave Questions",
                [
                    "How many casual leaves do I get? Every confirmed employee receives 12 "
                    "casual leaves per leave year.",
                    "How many sick leaves do I get? Every confirmed employee receives 15 sick "
                    "leaves per leave year.",
                    "Can I carry forward my casual leave? No. Casual leave lapses at the end of "
                    "the leave year. Only earned leave can be carried forward, up to 10 days.",
                    "How do I apply for leave? Employees must submit a leave request through the "
                    "ACME HR portal. Email and verbal requests are not valid.",
                    "How far in advance should I apply? At least seven calendar days in advance "
                    "for leave of three or more days.",
                ],
            ),
            (
                "2. Work From Home Questions",
                [
                    "How many days can I work from home? Up to 2 days per week under the hybrid "
                    "work model.",
                    "Which days are office days? Tuesday and Thursday are team anchor days on "
                    "which everyone is expected in the office.",
                    "Can new joiners work from home? Not during the first 60 days, which are "
                    "worked from the office to support onboarding.",
                    "Can I work from another city? Yes, for up to 15 working days without special "
                    "approval. Longer periods need department head approval.",
                ],
            ),
            (
                "3. Payroll and Benefits Questions",
                [
                    "When is salary credited? On the last working day of each month.",
                    "Where do I find my payslip? In the ACME HR portal from the first working "
                    "day of the following month.",
                    "What is my medical insurance cover? A floater sum insured of INR 5,00,000 "
                    "per family per year, covering spouse and up to two children.",
                    "Can I add my parents to the insurance? Yes, at an additional annual premium "
                    "of INR 12,000.",
                    "What is the learning allowance? INR 25,000 per employee per year.",
                ],
            ),
            (
                "4. Attendance Questions",
                [
                    "What are the core hours? 10:00 AM to 5:00 PM.",
                    "What happens if I arrive late? Three late arrivals in a calendar month "
                    "result in a deduction of half a day of casual leave.",
                    "How do I fix a missed swipe? Submit an attendance regularisation in the "
                    "ACME HR portal within five working days.",
                ],
            ),
            (
                "5. Joining and Exit Questions",
                [
                    "How long is probation? 6 months from the date of joining.",
                    "What is the notice period? 30 days during probation and 60 days after "
                    "confirmation.",
                    "Can I encash leave when I resign? Yes, up to 15 earned leaves are encashable "
                    "at the time of resignation, calculated on basic salary.",
                    "Who do I contact for HR help? Raise a ticket in the ACME HR portal; the "
                    "first response comes within one working day.",
                ],
            ),
        ],
    ),
}


def _styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "DocTitle", parent=base["Title"], fontSize=20, spaceAfter=6, leading=24
        ),
        "subtitle": ParagraphStyle(
            "DocSubtitle",
            parent=base["Normal"],
            fontSize=10.5,
            textColor="#555555",
            spaceAfter=18,
        ),
        "heading": ParagraphStyle(
            "SectionHeading",
            parent=base["Heading1"],
            fontSize=15,
            spaceBefore=0,
            spaceAfter=12,
        ),
        "body": ParagraphStyle(
            "BodyJustified",
            parent=base["BodyText"],
            fontSize=11,
            leading=16,
            alignment=TA_JUSTIFY,
            spaceAfter=10,
        ),
        "footer": ParagraphStyle(
            "Footer", parent=base["Normal"], fontSize=8.5, textColor="#888888"
        ),
    }


def _build_pdf(path: Path, subtitle: str, sections: List[Section]) -> None:
    styles = _styles()
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=2.2 * cm,
        rightMargin=2.2 * cm,
        topMargin=2.2 * cm,
        bottomMargin=2.2 * cm,
        title=path.stem.replace("_", " ").title(),
        author=f"{COMPANY} - People Operations",
    )

    story: List = []
    for index, (heading, paragraphs) in enumerate(sections):
        if index == 0:
            story.append(Paragraph(path.stem.replace("_", " ").title(), styles["title"]))
            story.append(Paragraph(f"{COMPANY} | {subtitle}", styles["subtitle"]))

        story.append(Paragraph(heading, styles["heading"]))

        bullets = [p for p in paragraphs if len(p) < 130 and p.count(". ") == 0]
        if len(bullets) == len(paragraphs) and len(paragraphs) > 3:
            story.append(
                ListFlowable(
                    [ListItem(Paragraph(p, styles["body"])) for p in paragraphs],
                    bulletType="bullet",
                    leftIndent=16,
                )
            )
        else:
            for paragraph in paragraphs:
                story.append(Paragraph(paragraph, styles["body"]))

        story.append(Spacer(1, 10))
        story.append(
            Paragraph(
                f"{COMPANY} - Internal HR document - fictional sample data", styles["footer"]
            )
        )
        if index < len(sections) - 1:
            story.append(PageBreak())

    doc.build(story)


def generate(output_dir: Path = OUTPUT_DIR) -> List[Path]:
    """Write every sample document and return the created paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    created: List[Path] = []
    for filename, (subtitle, sections) in DOCUMENTS.items():
        path = output_dir / filename
        _build_pdf(path, subtitle, sections)
        created.append(path)
        print(f"  created {path.name} ({len(sections)} pages)")
    return created


if __name__ == "__main__":
    print(f"Generating fictional HR documents for {COMPANY} in {OUTPUT_DIR}")
    paths = generate()
    print(f"Done. {len(paths)} document(s) written.")
