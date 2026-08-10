"""Load the Milestone-2 gold set and reshape it into the production contract.

The gold records were annotated before `parsed_resume_schema.json` settled, so
three field names differ. Reconciling them here — rather than loosening the
schema — keeps the production contract untouched and makes the mismatch a
single, reviewable function.

    gold                    schema
    ----------------------  ----------------------
    experience[].title      experience[].job_title
    experience[].is_current experience[].current_role
    projects[].tech         projects[].technologies

Annotation bookkeeping (`id`, `category`, `eval_split`, `pdf`, `_annotated`) is
metadata about the example, not part of the profile, so it travels as dataset
inputs and never as reference output.
"""

from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from src.resume_parsing.internal.location import locality_only

GOLD_DIR = Path(
    os.getenv(
        "RESUME_GOLD_DIR",
        Path.home() / "workspace/iitm/dsai/Milestone_2_Resume_Parsing/final_dataset",
    )
)
GOLD_JSONL = GOLD_DIR / "gold.jsonl"
DESCRIPTION_CORRECTIONS_JSONL = (
    Path(__file__).resolve().parent / "data" / "gold_description_corrections_v001.jsonl"
)
CERTIFICATION_SECTION_POLICY_JSONL = (
    Path(__file__).resolve().parent
    / "data"
    / "gold_certification_dedicated_sections_v001.jsonl"
)
SKILL_SECTION_POLICY_JSONL = (
    Path(__file__).resolve().parent / "data" / "gold_skill_sections_v001.jsonl"
)
CORRECTED_PROFILES_JSONL = (
    Path(__file__).resolve().parent / "data" / "gold_corrected_profiles_v001.jsonl"
)

# Source-image-verified corrections to the historical Milestone-2 annotations.
# Keeping them here makes the benchmark change explicit and reviewable without
# silently rewriting the original annotation artifact.
GOLD_CORRECTIONS_VERSION = (
    "education_source_review_v001_source_faithful_skills_v002_"
    "project_certification_source_review_v001_description_ocr_review_v001_"
    "certification_dedicated_sections_v001_skill_sections_v001_"
    "corrected_profiles_v001_reviewed_skill_certification_overlays_v003"
)


def _load_corrected_profiles() -> dict[str, dict]:
    profiles: dict[str, dict] = {}
    for line_number, line in enumerate(
        CORRECTED_PROFILES_JSONL.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        row = json.loads(line)
        resume_id = row["resume_id"]
        if resume_id in profiles:
            raise ValueError(
                f"Duplicate corrected profile at line {line_number}: {resume_id}"
            )
        profiles[resume_id] = row["profile"]
    return profiles


_CORRECTED_PROFILES = _load_corrected_profiles()


def _load_description_corrections() -> dict[str, dict[int, str]]:
    corrections: dict[str, dict[int, str]] = {}
    if not DESCRIPTION_CORRECTIONS_JSONL.exists():
        return corrections
    for line_number, line in enumerate(
        DESCRIPTION_CORRECTIONS_JSONL.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        row = json.loads(line)
        resume_id = row["resume_id"]
        index = int(row["experience_index"])
        if index in corrections.setdefault(resume_id, {}):
            raise ValueError(
                f"Duplicate description correction at line {line_number}: "
                f"{resume_id}[{index}]"
            )
        corrections[resume_id][index] = row["corrected_description"]
    return corrections


_DESCRIPTION_CORRECTIONS = _load_description_corrections()


def _load_skill_section_policy() -> dict[str, list[str]]:
    policy: dict[str, list[str]] = {}
    for line_number, line in enumerate(
        SKILL_SECTION_POLICY_JSONL.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        row = json.loads(line)
        resume_id = row["resume_id"]
        if resume_id in policy:
            raise ValueError(
                f"Duplicate skill-section policy at line {line_number}: {resume_id}"
            )
        policy[resume_id] = list(row["skills"])
    return policy


_SKILL_SECTION_CORRECTIONS = _load_skill_section_policy()


def _load_certification_section_policy() -> dict[str, set[int]]:
    policy: dict[str, set[int]] = {}
    for line_number, line in enumerate(
        CERTIFICATION_SECTION_POLICY_JSONL.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        row = json.loads(line)
        resume_id = row["resume_id"]
        if resume_id in policy:
            raise ValueError(
                f"Duplicate certification policy at line {line_number}: {resume_id}"
            )
        policy[resume_id] = {int(index) for index in row["retained_indices"]}
    return policy


_CERTIFICATION_SECTION_POLICY = _load_certification_section_policy()
_EDUCATION_CORRECTIONS = {
    "automobile__7b9fa0558115d57f": {
        0: {
            "degree": "Advanced Technical Certificate",
            "field": "Automotive Technology",
        },
    },
    "sql_developer__Image_97": {
        0: {"start_year": "2007", "end_year": "Ongoing"},
    },
}

_EDUCATION_REPLACEMENTS: dict[str, list[dict]] = {
    "education__135": [
        {
            "degree": "Master of Arts",
            "field": "Special Education, Behavior Analysis",
            "institution": "Brandman University",
            "start_year": None,
            "end_year": "2017",
        },
        {
            "degree": "Mild/Mod Special Education Preliminary Credential",
            "field": "Education Specialist",
            "institution": "Brandman University",
            "start_year": None,
            "end_year": "2017",
        },
        {
            "degree": "Bachelor of Arts",
            "field": "Psychology",
            "institution": "California State University - San Marcos",
            "start_year": None,
            "end_year": "2013",
        },
    ],
}

# Resume-specific replacements for historical skill annotations that bundled
# multiple skills or stored proficiency framing. The source gold.jsonl remains
# untouched; this versioned layer makes the benchmark migration auditable.
_ATOMIC_SKILL_CORRECTIONS: dict[str, dict[str, list[str]]] = {
    "sap_developer__Image_100": {
        "HANA Modeling (Attribute, Analytic, Calculation views)": [
            "HANA Modeling", "Attribute Views", "Analytic Views", "Calculation Views",
        ],
        "HANA Schemas, Synonyms, Sequences, Triggers": [
            "HANA Schemas", "Synonyms", "Sequences", "Triggers",
        ],
    },
    "operations_manager__a9abc2e5f3eb4af2": {
        "Verbal, written and presentation skills": [
            "Verbal Communication", "Written Communication", "Presentation Skills",
        ],
    },
    "testing__Image_4": {"Database (Oracle, MS SQL)": ["Oracle", "Microsoft SQL Server"]},
    "database__129": {
        "SSMS / SSRS / SSAS / PowerBI": ["SSMS", "SSRS", "SSAS", "Power BI"],
    },
    "consultant__eb58939c1a28881c": {"Strong Communication": ["Communication"]},
    "architect__38d167423f55cd85": {
        "Atkins standards, policies, codes and procedures": [
            "Atkins Standards", "Atkins Policies", "Atkins Codes", "Atkins Procedures",
        ],
        "Performance, reliability, scalability, security tactics": [
            "Performance Tactics", "Reliability Tactics", "Scalability Tactics",
            "Security Tactics",
        ],
        "Prosuite products (ProEHR, Practice Management, Allscripts Interface Engine)": [
            "ProEHR", "Practice Management", "Allscripts Interface Engine",
        ],
    },
    "digital_media__70": {
        "Microsoft Office Suite (Word, Excel, PowerPoint, Outlook, LiveCycle)": [
            "Microsoft Word", "Microsoft Excel", "Microsoft PowerPoint",
            "Microsoft Outlook", "Adobe LiveCycle",
        ],
        "Adobe Creative Suite (Premiere Pro, Dreamweaver, Photoshop, InDesign, After Effects, Illustrator, Media Encoder)": [
            "Adobe Premiere Pro", "Adobe Dreamweaver", "Adobe Photoshop",
            "Adobe InDesign", "Adobe After Effects", "Adobe Illustrator",
            "Adobe Media Encoder",
        ],
    },
    "data_science__33": {
        "Predictive Analytics (Machine Learning, Deep Learning, Forecasting)": [
            "Predictive Analytics", "Machine Learning", "Deep Learning", "Forecasting",
        ],
    },
    "education__f89bfd216550e1e5": {
        "Excellent Communication Skills": ["Communication"],
        "Knowledge of Child Development": ["Child Development"],
    },
    "designer__103": {
        "Schematics, design development & construction documents": [
            "Schematics", "Design Development", "Construction Documents",
        ],
        "Project management (residential, commercial, hospitality)": [
            "Project Management", "Residential Projects", "Commercial Projects",
            "Hospitality Projects",
        ],
    },
    "business_analyst__68e6eed269bdf1cf": {
        "Requirement elicitation (JAD, BRD)": ["Requirement Elicitation", "JAD", "BRD"],
    },
    "electrical_engineer__492c362b2d2f2180": {
        "Communication protocols (I2C, SPI, UART)": ["I2C", "SPI", "UART"],
    },
    "business_analyst__7e5f0138ac0c3411": {
        "Agile methodologies (Scrum, Kanban, Scrumban, XP, V model)": [
            "Agile Methodologies", "Scrum", "Kanban", "Scrumban", "XP", "V-Model",
        ],
    },
    "bpo__Image_39": {
        "E2E understanding of Liner Operations & Intermodal processes": [
            "Liner Operations", "Intermodal Processes",
        ],
    },
    "pmo__9036cb9577d9358b": {
        "Working with IT Project managers and development teams": [],
    },
    "devops_engineer__57": {
        "Cloud (AWS, Google Cloud)": ["AWS", "Google Cloud Platform"],
        "Virtualization (VMware, Xen, KVM)": ["VMware", "Xen", "KVM"],
        "Automation (Jenkins, Ansible, Selenium)": ["Jenkins", "Ansible", "Selenium"],
        "Version control (GitHub, BitBucket, Stash, Gitlab)": [
            "GitHub", "Bitbucket", "Stash", "GitLab",
        ],
        "RAID, SAN, NAS, NFS, SAMBA": ["RAID", "SAN", "NAS", "NFS", "Samba"],
        "LDAP, AD, Kerberos": ["LDAP", "Active Directory", "Kerberos"],
    },
    "web_designing__42ea741f515ea544": {
        "JavaScript (React, jQuery)": ["JavaScript", "React", "jQuery"],
    },
    "food_beverages__91a4d423c431ba31": {
        "Trained in liquor, wine and food service": [
            "Liquor Service", "Wine Service", "Food Service",
        ],
        "In-depth food and wine knowledge": ["Food Knowledge", "Wine Knowledge"],
    },
    "electrical_engineer__Image_90": {
        "Reliability methodologies (RCM, TPM, Spare Parts Management)": [
            "RCM", "TPM", "Spare Parts Management",
        ],
    },
    "web_designing__Image_19": {
        "Handmade Clothes (Embroidery, Weaving, Beadwork)": [
            "Embroidery", "Weaving", "Beadwork",
        ],
        "Formal Wear (Weddings, Celebrity Events)": [
            "Formal Wear", "Wedding Wear", "Celebrity Event Wear",
        ],
    },
    "mechanical_engineer__f8cab5066475ed7d": {
        "2D, 3D Solid Modeling": ["2D Solid Modeling", "3D Solid Modeling"],
        "Research, Design & Development": ["Research", "Design", "Development"],
    },
    "java_developer__4aed1ef936afe86a": {
        "Version Control (Git, SVN)": ["Git", "SVN"],
    },
    "sap_developer__a608c468bcfa43dc": {
        "ETL concepts and tools (Business Objects Data Services)": [
            "ETL", "BusinessObjects Data Services",
        ],
    },
    "information_technology__105": {
        "Project Management (Prince2, PMP)": ["Project Management", "PRINCE2", "PMP"],
    },
    "database__87": {
        "Computer proficient (Mac & Windows)": ["macOS", "Microsoft Windows"],
    },
    "testing__Image_58": {
        "Test Management Tools (QC, TD)": ["Quality Center", "TestDirector"],
    },
    "java_developer__8ac728ea5cb5894e": {
        "X query, XSL": ["XQuery", "XSL"],
        "DevOps tools (Jenkins, Docker)": ["Jenkins", "Docker"],
    },
    "react_developer__152": {
        "JEE Technologies (JSP, JSTL, Servlets, JPA, Web Services, JMS, JavaScript, ExtJS, jQuery, JSON)": [
            "JEE", "JSP", "JSTL", "Java Servlets", "JPA", "Web Services", "JMS",
            "JavaScript", "Ext JS", "jQuery", "JSON",
        ],
        "Spring (IOC, AOP, MVC, Transactions, Security, Cloud)": [
            "Spring", "Inversion of Control", "Aspect-Oriented Programming", "Spring MVC",
            "Spring Transactions", "Spring Security", "Spring Cloud",
        ],
        "SQL (Oracle, MySQL)": ["SQL", "Oracle", "MySQL"],
        "NoSQL (Cassandra, MongoDB, Redis)": ["NoSQL", "Cassandra", "MongoDB", "Redis"],
        "AWS (EC2, EBS, S3, RDS)": ["AWS", "Amazon EC2", "Amazon EBS", "Amazon S3", "Amazon RDS"],
    },
    "devops_engineer__142": {
        "Monitoring (Kibana, Prometheus, Data Dog)": ["Kibana", "Prometheus", "Datadog"],
        "Automation / Provisioning / Configuration Management (Ansible)": ["Ansible"],
        "Cloud (AWS, Azure, GCP)": ["AWS", "Microsoft Azure", "Google Cloud Platform"],
        "CI/CD (Jenkins, Bamboo, GitLab)": ["CI/CD", "Jenkins", "Bamboo", "GitLab"],
        "Version Control (Github, Bitbucket)": ["GitHub", "Bitbucket"],
        "Atlassian Tools (JIRA, Confluence)": ["Jira", "Confluence"],
        "Containerization (Docker, Kubernetes)": ["Docker", "Kubernetes"],
    },
    "accountant__44": {
        "Microsoft Word, Excel, Access, PowerPoint, Outlook": [
            "Microsoft Word", "Microsoft Excel", "Microsoft Access",
            "Microsoft PowerPoint", "Microsoft Outlook",
        ],
    },
    "advocate__ba77440de8f99831": {
        "Knowledge of Federal and State Laws": ["Federal Law", "State Law"],
    },
    "building_construction__Image_97": {
        "Knowledge of construction codes": ["Construction Codes"],
    },
    "management__Image_29": {
        "Strong interpersonal skills": ["Interpersonal Skills"],
        "Strong communicator": ["Communication"],
    },
}

_CERTIFICATION_CORRECTIONS: dict[str, list[dict]] = {
    "sql_developer__Image_97": [
        {
            "name": "Technology Architect Certification",
            "issuer": "Accenture",
            "year": None,
        },
        {
            "name": "OCP 12c and Oracle GoldenGate Implementation Specialist",
            "issuer": "Oracle",
            "year": None,
        },
    ],
    "information_technology__105": [
        {
            "name": "CISA | CERTIFIED INFORMATION SYSTEM AUDITOR",
            "issuer": "ISACA",
            "year": "2012",
        },
        {
            "name": "PRINCE2 | PROJECT MANAGEMENT",
            "issuer": "APMG-INTERNATIONAL",
            "year": "2012",
        },
        {
            "name": "ITIL FOUNDATION | IT SERVICE MANAGEMENT",
            "issuer": "APMG-INTERNATIONAL",
            "year": "2011",
        },
    ],
    "etl_developer__92": [
        {
            "name": "Informatica power center developer 9.x",
            "issuer": None,
            "year": None,
        },
        {
            "name": "PMP - Project Management Professional",
            "issuer": None,
            "year": "2018",
        },
    ],
    "digital_media__70": [
        {
            "name": "Visual Communications",
            "issuer": "University of Phoenix",
            "year": "2010",
        },
    ],
    "automobile__7b9fa0558115d57f": [{
        "name": "ASE Certified Mechanic",
        "issuer": "National Institute for Automotive Service Excellence",
        "year": None,
    }],
    "civil_engineer__3e1ceee0957c9c33": [
        {
            "name": "Project Management Professional (PMP)",
            "issuer": "PMI - USA",
            "year": None,
        },
        {"name": "Advanced Project Management", "issuer": None, "year": None},
        {"name": "Risk Management", "issuer": None, "year": None},
    ],
    "data_science__33": [
        {
            "name": "Artificial Intelligence Certificate",
            "issuer": "Columbia Univ.",
            "year": "2019",
        },
        {
            "name": "Data to Insights Prof. Certificate",
            "issuer": "MIT",
            "year": "2017",
        },
        {
            "name": "HIPPA & General Clinical Practices",
            "issuer": None,
            "year": "2017",
        },
        {
            "name": "Lean & Six Sigma",
            "issuer": "Navistar",
            "year": "2016",
        },
    ],
    "designer__103": [
        {"name": "NCIDQ National Certification", "issuer": "NCIDQ", "year": None},
        {
            "name": "Connecticut Registered Interior Designer License",
            "issuer": None,
            "year": None,
        },
        {"name": "Florida License", "issuer": None, "year": None},
    ],
    "education__135": [
        {"name": "Texas State Teaching Certification", "issuer": None, "year": "2021"},
        {
            "name": "Behavior Intervention Training Series (NBITS)",
            "issuer": "North County Consortium for Special Education (NCCSE)",
            "year": None,
        },
        {
            "name": "TEACCH (Treatment and Education of Autistic and Communication-Handicapped Children)",
            "issuer": None,
            "year": None,
        },
        {
            "name": "Tier 1 - Tier 3 Supports for All Students Evidenced Based Practice - Video Modeling",
            "issuer": None,
            "year": None,
        },
        {
            "name": "Self and Match Positive Behavioral Supports Training",
            "issuer": None,
            "year": None,
        },
        {"name": "The Zones of Regulation", "issuer": None, "year": None},
        {
            "name": "First Aid Certified/CPR Certified (Infant/Child/Adult)",
            "issuer": None,
            "year": None,
        },
        {
            "name": "CPI Trained (Crisis Prevention Intervention)",
            "issuer": None,
            "year": None,
        },
        {
            "name": "Writing Effective and Compliant Individualized Education Plans (IEPs)",
            "issuer": None,
            "year": None,
        },
        {
            "name": "Supporting English Learners in the Classroom",
            "issuer": None,
            "year": None,
        },
        {
            "name": "Cognitively Guided Instruction (CGI) Training Year 1, Grades 3-5",
            "issuer": None,
            "year": None,
        },
        {
            "name": "Development and Writing of Behavior Intervention Plans (BIPs)",
            "issuer": None,
            "year": None,
        },
        {
            "name": "Learning Headquarters Writing Professional Development",
            "issuer": None,
            "year": None,
        },
        {
            "name": "Next Generation Science Standards (NGSS) Training",
            "issuer": None,
            "year": None,
        },
        {"name": "i-Ready Mathematics Training", "issuer": None, "year": None},
        {"name": "Behavior is Communication Training", "issuer": None, "year": None},
        {
            "name": "Functional Behavior Assessment (FBA) Implementation Training",
            "issuer": None,
            "year": None,
        },
        {"name": "AAC / Proloquo Training", "issuer": None, "year": None},
    ],
    "mechanical_engineer__f8cab5066475ed7d": [
        {"name": "Confined Space Entry", "issuer": None, "year": None},
        {"name": "Fall Protection", "issuer": None, "year": None},
    ],
    "management__35": [
        {"name": name, "issuer": None, "year": year}
        for name, year in [
            ("Project Management Professional (PMP)", "2018"),
            ("Certified Hazardous Materials Manager (CHMM)", "2012"),
            ("Resource Conservation and Recovery Act (RCRA) - 16hrs.", "2021"),
            ("Department of Transportation (DOT) - 8hrs.", "2021"),
            ("40 hr. HAZWOPER Refresher - 8hrs.", "2020"),
            ("Powered Lift Truck - 4hrs.", "2021"),
            ("Confined Space - 3hrs.", "2021"),
            ("NASA Environmental Management System Training – 1hr.", "2021"),
            ("GRC Storm Water Management Program (SWMP) – 1hr.", "2021"),
            (
                "GRC Spill Prevention, Control, and Countermeasure (SPCC) and "
                "Aboveground Storage Tank (AST) Training – 1hr.",
                "2021",
            ),
            ("Personal Protective Equipment (PPE) – 1hr.", "2020"),
            ("Records Management – 1hr.", "2020"),
            ("Bloodborne Pathogens - 1hr.", "2020"),
            ("Lockout/Tagout – 1hr.", "2020"),
            ("Respiratory Protection Refresher - 2hrs.", "2020"),
            ("HazCom – 1hr.", "2019"),
            ("Hearing Conservation – 1 hr.", "2020"),
            ("Lead, and Asbestos Awareness – 1hr.", "2019"),
            ("Fire Extinguisher Training – 1hr.", "2019"),
            ("CPR/AED", "2021"),
            ("Explosive Handler's", "2018"),
            ("Commercial Driver's License (CDL) Class C, HazMat Endorsement", "2018"),
            ("NASA Mishap, Root Cause Analysis – 1hr.", "2011"),
            ("NASA Mishap Investigation Roles and Responsibilities – 1hr.", "2011"),
            ("NASA Completing the Investigation and Mishap Report – 1 hr.", "2011"),
            ("NASA Overview of Mishap Investigations – 1hr.", "2011"),
            ("GRC Underground Storage Tank (UST) Training – 1hr.", "2011"),
            ("Foreign Object Debris (FOD) – 1hr.", "2007"),
            ("FEMA Intro. to Incident Command System – 2hrs.", "2007"),
            ("FEMA Intro. to Incident Command System, I-110 for Schools - 4hrs.", "2007"),
            ("FEMA ICS for Single Resources and Initial Action Incident - 4hrs.", "2007"),
            ("Advanced Hazardous Waste Management – 16hrs.", "2005"),
            ("Resource Conservation and Recovery Act (RCRA) Train the Trainer – 1hr.", "2005"),
            ("Department of Transportation (DOT) Train the Trainer – 1hr.", "2005"),
        ]
    ],
    "operations_manager__4cfe28452173108e": [
        {"name": "Basic Electricity 101 Certification", "issuer": None, "year": None},
        {"name": "Class B CDL", "issuer": None, "year": None},
        {"name": "Hazmat Training", "issuer": None, "year": None},
        {"name": "First Aid Certified", "issuer": None, "year": None},
    ],
}

_PROJECT_CORRECTIONS: dict[str, list[dict]] = {
    "management__35": [
        {"name": name, "description": None, "technologies": []}
        for name in [
            "J6 VR Incident Environmental Cleanup",
            "J5 Asbestos Abatement",
            "Oil Water Separator",
            "Cooling Tower 5 Basin Cleaning",
            "10x10 Waterline Repair",
            "Storm Basin Remediation",
            "Cooling Tower 1 Basin Cleaning",
            "Lead Paint Remediation, B24 Demo",
            "Red Water Spill Response",
            "Environmental Site Assessments, B35 Demo and Storm Water Phase II",
            "Remediation of Lead Dust at the Hangar",
            "Remediation of Lead Dust at B125 Propulsion Systems Laboratory",
            "Remediation of the West Industrial Waste Basin",
            "Remediation of the Zero Gravity Drop Tower",
        ]
    ],
    "consultant__eb58939c1a28881c": [
        {
            "name": "Innovative Strategies in Change Management",
            "description": (
                "Presented a paper on \"Innovative Strategies in Change Management\" "
                "during the 2019 Annual Consultants Conference, Washington"
            ),
            "technologies": [],
        },
    ],
    "designer__91": [
        {
            "name": "US Patent No: US 8,864,250 B2; Universal crisper frame able to accommodate a variety of crisper configurations",
            "description": "Oct. 21, 2014 US Patent No: US 8,864,250 B2; Universal crisper frame able to accommodate a variety of crisper configurations",
            "technologies": [],
        },
        {
            "name": "US Patent No: US 7,610,774 B2; Refrigerator door with can and bottle holder",
            "description": "Nov. 3, 2009 US Patent No: US 7,610,774 B2; Refrigerator door with can and bottle holder",
            "technologies": [],
        },
        {
            "name": "US Patent No: US 7,490,916 B2; Refrigerator with multi-piece mullion having stepped offset",
            "description": "Feb. 17, 2009 US Patent No: US 7,490,916 B2; Refrigerator with multi-piece mullion having stepped offset",
            "technologies": [],
        },
        {
            "name": "US Patent No: US 7,410,230 B2; Refrigerator with multi-piece mullion having stepped offset",
            "description": "Aug. 12, 2008 US Patent No: US 7,410,230 B2; Refrigerator with multi-piece mullion having stepped offset",
            "technologies": [],
        },
        {
            "name": "US Patent No: US 7,284,392 B2; Refrigerator icemaker with wiring hooks",
            "description": "Oct. 23, 2007 US Patent No: US 7,284,392 B2; Refrigerator icemaker with wiring hooks",
            "technologies": [],
        },
        {
            "name": "US Patent No: US 7,266,973 B2; Refrigerator with improved icemaker having airflow control",
            "description": "Sept. 11, 2007 US Patent No: US 7,266,973 B2; Refrigerator with improved icemaker having airflow control",
            "technologies": [],
        },
        {
            "name": "US Patent No: US 7,266,957 B2; Refrigerator with tilted icemaker",
            "description": "Sept. 11, 2007 US Patent No: US 7,266,957 B2; Refrigerator with tilted icemaker",
            "technologies": [],
        },
        {
            "name": "US Patent No: US 6,918,259 B2; Air circulation and filtration system for a refrigerator",
            "description": "July 19, 2005 US Patent No: US 6,918,259 B2; Air circulation and filtration system for a refrigerator",
            "technologies": [],
        },
        {
            "name": "US Patent No: US 6,772,606 B2; Method and apparatus for a plastic evaporator fan shroud assembly",
            "description": "Aug. 10, 2004 US Patent No: US 6,772,606 B2; Method and apparatus for a plastic evaporator fan shroud assembly",
            "technologies": [],
        },
    ],
    "sql_developer__Image_97": [
        {
            "name": "ROR - ReactJS| GraphQL|Redux in practice",
            "description": "Presenter on 4Developers conference (2017)",
            "technologies": ["ROR", "ReactJS", "GraphQL", "Redux"],
        },
        {
            "name": "Mastering Oracle GoldenGate Technology",
            "description": "I authored a 623 pages long book on mastering Oracle GoldenGate Technology. This was published in 2016 by Apress, New York.",
            "technologies": ["Oracle GoldenGate"],
        },
    ],
    "arts__Image_12": [
        {
            "name": "Not Sent Letter Art",
            "description": "Contributing Artist",
            "technologies": [],
        },
        {
            "name": "Best Before: Archivised",
            "description": "BFA 4th year Project - Audain Gallery 2017",
            "technologies": [],
        },
        {
            "name": "Best Before: Archivised",
            "description": "BFA 3rd year Project - Audain Gallery 2016",
            "technologies": [],
        },
        {
            "name": "SFU FCAT Undergraduate Conference",
            "description": "Presenter - Surrey, 2016 & 2017",
            "technologies": [],
        },
        {
            "name": "17th Annual European Festival",
            "description": "Exhibitor - 2014",
            "technologies": [],
        },
    ],
    "etl_developer__92": [
        {
            "name": "Tech Roadmap",
            "description": (
                "This is a multi-year initiative to enhance our technology, providing "
                "needed technology and personnel resources to accomplish prioritized "
                "projects. The objective of the project is to assess the current "
                "technology landscape for Corporate Audit and Credit Review (CACR) and "
                "design a framework to drive the technology vision for the next five "
                "years. The technology roadmap will help address pain points and drive "
                "a more integrated technology environment."
            ),
            "technologies": [],
        },
        {
            "name": "Data Lake",
            "description": (
                "Working on an enhanced data storage solution for CACR to gather and "
                "analyze data in a centralized repository for a diverse user group. "
                "This is currently built on Hadoop platform with multiple storage "
                "layers to support various data intakes."
            ),
            "technologies": ["Hadoop"],
        },
        {
            "name": "Audit Technology Laboratory",
            "description": (
                "In response to employee feedback and in support of our Innovation "
                "Strategy, I designed and built a technology virtual Lab environment "
                "to provide an open and collaborative work space for audit users to "
                "learn new tools and technologies within a dedicated environment. The "
                "Lab is an integrated platform that will allow you to leverage a range "
                "of tools in the current technology ecosystem."
            ),
            "technologies": [],
        },
        {
            "name": "Implementation of Automated Audit Testing",
            "description": (
                "Continued implementation of continuous audit automation testing to "
                "drive real time feedback to management on exceptions. Working on a "
                "stretched goal of 25% YoY growth from 2020 production."
            ),
            "technologies": [],
        },
    ],
    "designer__103": [
        {
            "name": "Hamptons Designer Show House, Dining Room",
            "description": (
                "Designer for Traditional Home and SouthHampton Hospital, "
                "Hamptons Designer Show House, Dining Room, 2013."
            ),
            "technologies": [],
        },
        {
            "name": "Gray house for the President of MIT",
            "description": "Designed the Gray house for the President of MIT, 2013.",
            "technologies": [],
        },
        {
            "name": "Do's Blow Dry Salon",
            "description": (
                "Serendipity Best of Fairfield County for Do's Blow Dry Salon, 2013."
            ),
            "technologies": [],
        },
        {
            "name": "3500 square foot office in the Chrysler Building",
            "description": (
                "Designed 3500 square foot office in the Chrysler Building, NYC, 2012."
            ),
            "technologies": [],
        },
    ],
    "web_designing__42ea741f515ea544": [
        {
            "name": "Geosearch Area Statistics",
            "description": (
                "Uses REST APIs from US Census, Zillow and other services to fetch "
                "information about an area (2015)."
            ),
            "technologies": ["REST APIs"],
        },
        {
            "name": "Feather",
            "description": "Lightweight alternative to CSS grid systems (2015).",
            "technologies": [],
        },
    ],
}


@dataclass(frozen=True, slots=True)
class GoldExample:
    resume_id: str
    category: str
    split: str
    pdf_path: Path
    profile: dict

    @property
    def inputs(self) -> dict:
        return {
            "resume_id": self.resume_id,
            "category": self.category,
            "pdf": str(self.pdf_path.relative_to(GOLD_DIR)),
        }


def load(split: str | None = "dev") -> list[GoldExample]:
    """Annotated gold records for one split, or all splits when `split` is None."""
    if not GOLD_JSONL.exists():
        raise FileNotFoundError(
            f"Gold set not found at {GOLD_JSONL}. Set RESUME_GOLD_DIR to the "
            "directory holding gold.jsonl and gold/."
        )

    examples = []
    for line in GOLD_JSONL.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if not record.get("_annotated"):
            continue
        if split is not None and record.get("eval_split") != split:
            continue
        if record["id"] not in _CORRECTED_PROFILES:
            raise ValueError(f"Missing corrected gold profile: {record['id']}")
        profile = deepcopy(_CORRECTED_PROFILES[record["id"]])
        # These two compact files are the actively reviewed overlays. Applying
        # them here keeps the materialized profile stable while ensuring that
        # approved manual-review changes are used by every scorer.
        if record["id"] in _SKILL_SECTION_CORRECTIONS:
            profile["skills"] = deepcopy(_SKILL_SECTION_CORRECTIONS[record["id"]])
        if record["id"] in _EDUCATION_REPLACEMENTS:
            profile["education"] = deepcopy(_EDUCATION_REPLACEMENTS[record["id"]])
        if record["id"] in _CERTIFICATION_CORRECTIONS:
            profile["certifications"] = deepcopy(_CERTIFICATION_CORRECTIONS[record["id"]])
        if record["id"] in _PROJECT_CORRECTIONS:
            profile["projects"] = deepcopy(_PROJECT_CORRECTIONS[record["id"]])
        examples.append(
            GoldExample(
                resume_id=record["id"],
                category=record["category"],
                split=record["eval_split"],
                pdf_path=GOLD_DIR / record["pdf"],
                profile=profile,
            )
        )
    return sorted(examples, key=lambda e: e.resume_id)


def apply_corrections(resume_id: str, profile: dict) -> dict:
    """Apply only corrections verified directly against the source resume image."""
    corrected = deepcopy(profile)
    if resume_id in _EDUCATION_REPLACEMENTS:
        corrected["education"] = deepcopy(_EDUCATION_REPLACEMENTS[resume_id])
    for index, values in _EDUCATION_CORRECTIONS.get(resume_id, {}).items():
        corrected["education"][index].update(values)
    if resume_id in _SKILL_SECTION_CORRECTIONS:
        corrected["skills"] = deepcopy(_SKILL_SECTION_CORRECTIONS[resume_id])
    # Skills are source-faithful section entries. Do not atomize or rewrite them
    # in gold loading; specialized skills scoring handles controlled matching.
    corrected["skills"] = list(dict.fromkeys(corrected.get("skills") or []))
    if resume_id in _CERTIFICATION_CORRECTIONS:
        corrected["certifications"] = deepcopy(_CERTIFICATION_CORRECTIONS[resume_id])
    retained_certification_indices = _CERTIFICATION_SECTION_POLICY.get(resume_id, set())
    corrected["certifications"] = [
        certification
        for index, certification in enumerate(corrected.get("certifications") or [])
        if index in retained_certification_indices
    ]
    if resume_id in _PROJECT_CORRECTIONS:
        corrected["projects"] = deepcopy(_PROJECT_CORRECTIONS[resume_id])
    for index, description in _DESCRIPTION_CORRECTIONS.get(resume_id, {}).items():
        if index >= len(corrected.get("experience") or []):
            raise ValueError(
                f"Description correction index out of range: {resume_id}[{index}]"
            )
        corrected["experience"][index]["description"] = description
    return corrected


_NON_ATOMIC_SKILL = re.compile(
    r"^(?:proficient|experienced|experience|knowledge|excellent|strong|ability|"
    r"trained\s+in|working\s+with)\b",
    re.IGNORECASE,
)


def atomic_skill_issues(skills: list[object]) -> list[str]:
    """Return obvious annotation-contract violations for gold-set review."""
    issues = []
    for value in skills:
        if not isinstance(value, str) or not value.strip():
            issues.append(repr(value))
            continue
        text = value.strip()
        if ";" in text or "," in text or _NON_ATOMIC_SKILL.search(text):
            issues.append(text)
    return issues


def to_profile(record: dict) -> dict:
    """One gold record, reshaped into a `parsed_resume_schema.json` object."""
    contact = record.get("contact") or {}
    return {
        "contact": {
            "name": contact.get("name"),
            "location": locality_only(contact.get("location")),
            "links": list(contact.get("links") or []),
        },
        "skills": list(record.get("skills") or []),
        "education": [
            {
                key: entry.get(key)
                for key in ("degree", "field", "institution", "start_year", "end_year")
            }
            for entry in record.get("education") or []
        ],
        "experience": [
            {
                "job_title": entry.get("title"),
                "company": entry.get("company"),
                "location": locality_only(entry.get("location")),
                "start_date": entry.get("start_date"),
                "end_date": entry.get("end_date"),
                "current_role": entry.get("is_current"),
                "description": entry.get("description"),
            }
            for entry in record.get("experience") or []
        ],
        "projects": [
            {
                "name": entry.get("name"),
                "description": entry.get("description"),
                "technologies": list(entry.get("tech") or []),
            }
            for entry in record.get("projects") or []
        ],
        "certifications": [
            {key: entry.get(key) for key in ("name", "issuer", "year")}
            for entry in record.get("certifications") or []
        ],
        "job_titles": list(record.get("job_titles") or []),
    }


EMPTY_PROFILE: dict = {
    "contact": {"name": None, "location": None, "links": []},
    "skills": [],
    "education": [],
    "experience": [],
    "projects": [],
    "certifications": [],
    "job_titles": [],
}
