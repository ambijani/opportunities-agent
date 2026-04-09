"""
Fast keyword-based pre-classifier.
Assigns job_type and category before hitting the Claude API.
Returns None for either field when the signal is ambiguous.
"""
import re
from database.models import Job

# ─── Job type signals ─────────────────────────────────────────────────────────

INTERNSHIP_SIGNALS = re.compile(
    r"\b(intern(ship)?|co[-\s]?op|summer\s+20\d\d|summer\s+program|"
    r"undergrad|undergraduate|underclassmen?|freshman|sophomore|junior)\b",
    re.IGNORECASE,
)

FULL_TIME_SIGNALS = re.compile(
    r"\b(full[-\s]?time|new\s+grad(uate)?|entry[-\s]?level|associate|"
    r"0[-–]\s*[12]\s+year|recent\s+grad(uate)?|junior\s+(engineer|developer|analyst))\b",
    re.IGNORECASE,
)

# ─── Category keyword sets ─────────────────────────────────────────────────────

CATEGORY_PATTERNS: list[tuple[str, re.Pattern]] = [
    (
        "cs-engineering-tech",
        re.compile(
            r"\b(software|engineer(ing)?|developer|swe|sde|data\s+(engineer|scientist|analyst)|"
            r"machine\s+learning|ml|ai|artificial\s+intelligence|cyber(security)?|"
            r"information\s+tech(nology)?|it\b|devops|cloud|backend|frontend|fullstack|"
            r"full[-\s]stack|product\s+(manager|management)|program(ming)?|computer\s+science|"
            r"firmware|embedded|hardware|electrical|mechanical|robotics|aerospace)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "business-finance-banking",
        re.compile(
            r"\b(finance|financial|banking|investment\s+bank(ing)?|private\s+equity|"
            r"venture\s+capital|hedge\s+fund|accounting|audit|tax|treasury|"
            r"corporate\s+finance|equity\s+research|trading|fintech|cpa|cfa|actuar(y|ial)|"
            r"risk\s+(analyst|management)|credit|portfolio\s+manager|wealth\s+management|"
            r"commercial\s+bank(ing)?|capital\s+markets)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "consulting",
        re.compile(
            r"\b(consult(ing|ant|ancy)|strategy|strategic|advisory|management\s+consult|"
            r"mckinsey|bain|bcg|deloitte|accenture|kpmg|pwc|ey\b|ernst\s+&\s+young|"
            r"oliver\s+wyman|roland\s+berger|business\s+analyst)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "humanities-healthcare-medicine",
        re.compile(
            r"\b(healthcare|health\s+care|medical|medicine|clinical|hospital|nursing|"
            r"pharmacy|pre[-\s]?med|biology|biochemistry|chemistry|public\s+health|"
            r"psychology|social\s+work|policy|political\s+science|economics|journalism|"
            r"communications?|marketing|pr\b|public\s+relations|non[-\s]?profit|ngo|"
            r"education|teaching|research\s+(assistant|associate))\b",
            re.IGNORECASE,
        ),
    ),
    (
        "programs",
        re.compile(
            r"\b(fellowship|immersion|rotational|leadership\s+development|cohort|"
            r"scholarship|externship|diversity\s+(program|initiative)|"
            r"early\s+career\s+program|launch\s+program|explore\s+program|"
            r"associate\s+program|analyst\s+program|summer\s+institute)\b",
            re.IGNORECASE,
        ),
    ),
]


def classify(job: Job) -> Job:
    """
    Mutates job.job_type and job.category in-place if the keyword signal is clear.
    Returns the job with None fields left for Claude to handle.
    """
    text = f"{job.title} {job.company} {job.description} {job.source}"

    # ── job type ──────────────────────────────────────────────────────────────
    intern_hit = bool(INTERNSHIP_SIGNALS.search(text))
    ft_hit = bool(FULL_TIME_SIGNALS.search(text))

    if intern_hit and not ft_hit:
        job.job_type = "internship"
    elif ft_hit and not intern_hit:
        job.job_type = "full_time"
    # if both or neither hit → leave as None for Claude

    # ── category ──────────────────────────────────────────────────────────────
    matches: list[str] = []
    for category, pattern in CATEGORY_PATTERNS:
        if pattern.search(text):
            matches.append(category)

    if len(matches) == 1:
        job.category = matches[0]
    elif len(matches) > 1:
        # Take the first (highest-priority) match
        job.category = matches[0]
    # else leave as None for Claude

    return job
