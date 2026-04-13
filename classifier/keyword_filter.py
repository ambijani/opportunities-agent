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
    r"0[-–]\s*[12]\s+year|recent\s+grad(uate)?|junior\s+(engineer|developer|analyst)|"
    r"senior|sr\.?\s|lead\s|principal|staff\s+(engineer|scientist|developer|analyst)|"
    r"director|manager|head\s+of|vice\s+president|\bvp\b|"
    r"architect|specialist|consultant)\b",
    re.IGNORECASE,
)

# ─── Category keyword sets ─────────────────────────────────────────────────────
# Priority order matters: first match wins when multiple patterns fire.
# scholarships → programs → consulting → cs-engineering-tech →
# business-finance-banking → humanities-healthcare-medicine

CATEGORY_PATTERNS: list[tuple[str, re.Pattern]] = [
    (
        "scholarships",
        re.compile(
            r"\b(scholarship|bursary|financial\s+aid|"
            r"tuition\s+(assistance|reimbursement)|academic\s+award)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "programs",
        re.compile(
            r"\b(fellowship|immersion|rotational(\s+program)?|leadership\s+development|"
            r"cohort|externship|diversity\s+(program|initiative)|hackathon|summit|"
            r"early\s+career\s+program|launch\s+program|explore\s+program|"
            r"associate\s+program|analyst\s+program|summer\s+institute|"
            r"accelerator\s+program|incubator\s+program)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "consulting",
        re.compile(
            r"\b(consult(ing|ant|ancy)|management\s+consult|strategy\s+consult|"
            r"strategic\s+advisory|advisory\s+(role|position|analyst|associate)|"
            r"mckinsey|bain\b|bcg\b|deloitte|accenture|kpmg|pwc\b|ey\b|ernst\s+&\s+young|"
            r"oliver\s+wyman|roland\s+berger)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "cs-engineering-tech",
        re.compile(
            # SWE / dev
            r"\b(software\s+(engineer|developer|development)|swe\b|sde\b|"
            r"backend|frontend|fullstack|full[-\s]stack|mobile\s+(developer|engineer)|"
            r"ios\s+(developer|engineer)|android\s+(developer|engineer)|"
            r"program(ming)?|computer\s+science|"
            # Data analyst / scientist / engineer
            r"data\s+(engineer|scientist|analyst|engineering|analytics)|"
            r"analytics|business\s+intelligence|bi\s+(analyst|developer|engineer)|"
            # ML / AI
            r"machine\s+learning|ml\b|ai\b|artificial\s+intelligence|"
            r"deep\s+learning|nlp\b|natural\s+language\s+processing|computer\s+vision|"
            # Product management
            r"product\s+(manager|management)|"
            # Engineering & development (broad)
            r"engineer(ing)?\s+(intern|associate|analyst|lead|manager)|"
            r"firmware|embedded|hardware|electrical|mechanical|robotics|aerospace|"
            r"r\s*&\s*d\b|research\s+and\s+development|"
            # Cybersecurity
            r"cyber(security)?|security\s+(engineer|analyst|architect|specialist|intern)|"
            r"information\s+security|infosec|devsecops|"
            # DevOps / cloud / IT / systems
            r"devops|cloud\s+(engineer|architect|developer)|sre\b|site\s+reliability|"
            r"systems\s+(analyst|engineer|administrator|admin)|"
            r"network(ing)?\s+(engineer|admin|analyst)|"
            r"database\s+(admin|administrator|engineer|analyst)|"
            r"infrastructure|platform\s+engineer|"
            r"quality\s+assurance|qa\s+(engineer|analyst|tester)|"
            r"test\s+(engineer|automation|developer)|sdet\b|"
            r"tech(nology)?\s+(intern|analyst|manager|lead|specialist|director)|"
            r"information\s+tech(nology)?|"
            r"technical\s+(analyst|writer|lead|support|specialist)|"
            r"it\s+(analyst|manager|specialist|support|director|intern)\b)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "business-finance-banking",
        re.compile(
            # Accounting & finance / banking
            r"\b(finance|financial|banking|investment\s+bank(ing)?|private\s+equity|"
            r"venture\s+capital|hedge\s+fund|accounting|audit|tax|treasury|"
            r"corporate\s+finance|equity\s+research|trading|fintech|cpa|cfa|actuar(y|ial)|"
            r"risk\s+(analyst|management)|credit|portfolio\s+manager|wealth\s+management|"
            r"commercial\s+bank(ing)?|capital\s+markets|payroll|"
            r"accounts\s+(payable|receivable)|revenue\s+(analyst|associate)|"
            # Marketing
            r"marketing|market\s+(research|analyst)|brand\s+(manager|strategist|analyst)|"
            r"content\s+marketing|digital\s+marketing|growth\s+marketing|"
            # Business analyst
            r"business\s+analyst|"
            # Sales
            r"sales\s+(intern|analyst|associate|representative|manager)|"
            r"account\s+(executive|manager|representative)|business\s+development|"
            # Project management
            r"project\s+(manager|management|coordinator)|pmp\b|"
            # Management & executive
            r"management\s+(analyst|associate|trainee|intern)|"
            r"operations\s+(analyst|manager|intern|associate)|"
            # Supply chain
            r"supply\s+chain|logistics|procurement|purchasing\s+(analyst|manager|intern))\b",
            re.IGNORECASE,
        ),
    ),
    (
        "humanities-healthcare-medicine",
        re.compile(
            # Healthcare / medicine
            r"\b(healthcare|health\s+care|medical|medicine|clinical|hospital|nursing|"
            r"pharmacy|pre[-\s]?med|public\s+health|"
            r"biology|biochemistry|chemistry|psychology|"
            # Human resources
            r"human\s+resources|hr\s+(intern|analyst|generalist|manager|coordinator)|"
            r"talent\s+acquisition|recruit(er|ing|ment)|"
            # Creative & design
            r"graphic\s+design(er)?|ux\s+(designer|researcher)|ui\s+(designer|developer)|"
            r"visual\s+design(er)?|product\s+design(er)?|"
            r"creative\s+(director|designer|strategist|intern)|"
            r"motion\s+(designer|graphics)|brand\s+design|"
            # Arts & entertainment
            r"arts?\s+and\s+entertainment|art\s+director|media\s+(production|intern)|"
            r"film\s+(production|intern)|video\s+(editor|production)|"
            r"content\s+(creator|producer|strategist)|social\s+media\s+(manager|intern)|"
            # Customer service & support
            r"customer\s+(service|support|success|experience)|client\s+(service|support|success)|"
            r"help\s+desk|technical\s+support\s+specialist|"
            # Legal & compliance
            r"legal\s+(intern|analyst|associate|counsel|assistant)|paralegal|"
            r"compliance\s+(analyst|officer|intern|specialist)|regulatory\s+affairs|"
            # Public sector & government
            r"public\s+(sector|service|administration|affairs)|"
            r"government\s+(intern|analyst|affairs|relations)|"
            r"policy\s+(analyst|intern|associate)|political\s+science|"
            # Education & training
            r"education|teaching|teacher|tutor|instructional\s+design|"
            r"training\s+(specialist|coordinator|intern)|"
            # Misc social / nonprofit / comms
            r"social\s+work|journalism|communications?|pr\b|public\s+relations|"
            r"non[-\s]?profit|ngo|research\s+(assistant|associate))\b",
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
    # Only classify if not already set (e.g. by path-based scraper)
    if job.job_type is None:
        intern_hit = bool(INTERNSHIP_SIGNALS.search(text))
        ft_hit = bool(FULL_TIME_SIGNALS.search(text))

        if intern_hit and not ft_hit:
            job.job_type = "internship"
        elif ft_hit and not intern_hit:
            job.job_type = "full_time"
        # if both or neither hit → leave as None for Claude

    # ── category ──────────────────────────────────────────────────────────────
    # Only classify if not already set (e.g. by path-based scraper)
    if job.category is None:
        for category, pattern in CATEGORY_PATTERNS:
            if pattern.search(text):
                job.category = category
                break  # first match wins (priority order in CATEGORY_PATTERNS)

    return job
