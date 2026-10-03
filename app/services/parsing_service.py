from datetime import datetime
import re
from typing import Any, Dict, List, Optional, Set, Tuple


class ParsingService:
    """
    Deterministic rule-based resume parsing engine.
    Extracts contact info, skills, title, experience years, and education without requiring external LLMs.
    """

    KNOWN_SKILLS = [
        # Languages
        "Python", "JavaScript", "TypeScript", "Java", "C++", "C#", ".NET", "Go", "Golang",
        "Rust", "Ruby", "PHP", "Scala", "Kotlin", "Swift", "SQL", "HTML", "CSS", "Bash", "Shell",
        # Frameworks & Libraries
        "FastAPI", "Django", "Flask", "React", "Next.js", "Vue", "Angular", "Node.js", "Express",
        "Spring Boot", "PyTorch", "TensorFlow", "Scikit-Learn", "Pandas", "NumPy", "Keras",
        # Databases & Messaging
        "MongoDB", "PostgreSQL", "MySQL", "Redis", "Elasticsearch", "Cassandra", "DynamoDB",
        "Kafka", "RabbitMQ", "SQLite", "Atlas",
        # Cloud & DevOps
        "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Linux", "Git", "GitHub", "GitLab",
        "CI/CD", "Terraform", "Ansible", "Jenkins", "Nginx",
        # Concepts & Architecture
        "REST", "RESTful", "GraphQL", "Microservices", "System Design", "Agile", "Scrum",
        "Machine Learning", "Deep Learning", "NLP", "Vector Search", "PyMuPDF",
    ]

    # Titles ordered from most specific to least specific.
    # Generic titles like "Software Engineer" are at the end so they don't shadow specific ones.
    KNOWN_TITLES = [
        # Leadership / Architect
        "Lead Software Architect",
        "Principal Software Engineer",
        "Engineering Manager",
        "Solutions Architect",
        "Cloud Architect",
        # Senior Specialised
        "Senior Backend Engineer",
        "Senior Backend Developer",
        "Senior Frontend Engineer",
        "Senior Frontend Developer",
        "Senior Full Stack Engineer",
        "Senior Full Stack Developer",
        "Senior DevOps Engineer",
        "Senior Data Engineer",
        "Senior Data Scientist",
        "Senior Machine Learning Engineer",
        "Senior Software Engineer",
        "Senior Software Developer",
        # Mid-level Specialised
        "Backend Engineer",
        "Backend Developer",
        "Frontend Engineer",
        "Frontend Developer",
        "Full Stack Engineer",
        "Full Stack Developer",
        "DevOps Engineer",
        "Cloud Engineer",
        "Machine Learning Engineer",
        "ML Engineer",
        "Data Scientist",
        "Data Analyst",
        "Data Engineer",
        "QA Engineer",
        "Test Engineer",
        "Product Manager",
        "Mobile Developer",
        "iOS Developer",
        "Android Developer",
        "UI Developer",
        "UX Designer",
        # Junior Specialised
        "Junior Backend Developer",
        "Junior Frontend Developer",
        "Junior Full Stack Developer",
        "Junior Software Developer",
        "Junior Software Engineer",
        # Generic (lowest priority — used only as fallback)
        "Software Engineer",
        "Software Developer",
        "Web Developer",
        "Programmer",
    ]

    # Generic titles that should be replaced by a more specific skill-based inference
    _GENERIC_TITLES = {
        "Software Engineer", "Software Developer", "Web Developer", "Programmer",
        "Senior Software Engineer", "Senior Software Developer",
        "Junior Software Developer", "Junior Software Engineer",
    }

    # Skill-to-role inference mapping. Order matters: first match wins.
    _SKILL_ROLE_MAP = [
        # DevOps / Cloud
        ({"Docker", "Kubernetes", "Terraform", "Ansible", "CI/CD", "Jenkins"}, 3, "DevOps Engineer"),
        ({"AWS", "Azure", "GCP", "Terraform", "Kubernetes"}, 3, "Cloud Engineer"),
        # ML / Data
        ({"PyTorch", "TensorFlow", "Keras", "Scikit-Learn", "Deep Learning", "Machine Learning", "NLP"}, 2, "Machine Learning Engineer"),
        ({"Pandas", "NumPy", "Scikit-Learn", "Machine Learning"}, 2, "Data Scientist"),
        ({"Kafka", "Cassandra", "Elasticsearch", "DynamoDB", "Data Engineer"}, 2, "Data Engineer"),
        # Frontend
        ({"React", "Angular", "Vue", "Next.js", "CSS", "HTML", "TypeScript", "JavaScript"}, 3, "Frontend Developer"),
        # Backend
        ({"FastAPI", "Django", "Flask", "Spring Boot", "Express", "Node.js", "PostgreSQL", "MongoDB", "Redis"}, 3, "Backend Developer"),
        # Full Stack (both frontend + backend signals)
        ({"React", "Angular", "Vue", "Django", "FastAPI", "Flask", "Express", "Node.js"}, 3, "Full Stack Developer"),
        # Mobile
        ({"Swift", "Kotlin", "React Native", "Flutter"}, 2, "Mobile Developer"),
    ]

    DEGREE_PATTERNS = [
        r"(?:^|\b|\s)(?:Bachelor|B\.?S\.?|B\.?A\.?|B\.?Tech|B\.?E\.?|B\.?Sc|B\.?Com|BCA|BBA)(?:\b|\s)(?:\s*(?:of|in)\s*[\w\s]+)?",
        r"(?:^|\b|\s)(?:Master(?:s|'s)?|M\.?S\.?|M\.?A\.?|M\.?Tech|M\.?E\.?|M\.?Sc|M\.?B\.?A\.?|MCA)(?:\b|\s)(?:\s*(?:of|in)\s*[\w\s]+)?",
        r"(?:^|\b|\s)(?:Ph\.?D\.?|Doctorate|Doctor\s+of)(?:\b|\s)(?:\s*(?:of|in)\s*[\w\s]+)?",
    ]

    def extract_email(self, text: str) -> Optional[str]:
        """Extract primary email address from text."""
        match = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)
        return match.group(0).strip() if match else None

    def extract_phone(self, text: str) -> Optional[str]:
        """Extract phone number formatted in US or international notation."""
        match = re.search(
            r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
            text,
        )
        return match.group(0).strip() if match else None

    def extract_name(self, text: str) -> str:
        """Heuristically extract candidate name from the top lines of the resume."""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for line in lines[:6]:
            # Skip lines with contact markers
            if any(char in line for char in ["@", "http", "www.", "/", "\\", ":", "|"]):
                continue
            # Skip common generic headings
            if line.lower() in ["resume", "curriculum vitae", "cv", "summary", "profile", "contact"]:
                continue
            # Words count check for a valid name
            words = line.split()
            if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words if w.isalpha()):
                return line
        return lines[0] if lines else "Candidate"

    def _find_title_in_header(self, text: str) -> Optional[str]:
        """
        Look for an explicit job title in the resume header area (top 8 non-empty lines).
        Header titles are the strongest signal — candidates often put their role right under their name.
        Returns the most specific title found in the header, or None.
        """
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        header_text = " ".join(lines[:8])

        best_title: Optional[str] = None
        for title in self.KNOWN_TITLES:
            pattern = rf"\b{re.escape(title)}\b"
            if re.search(pattern, header_text, re.IGNORECASE):
                # Return the first (most specific) non-generic title found in the header
                if title not in self._GENERIC_TITLES:
                    return title
                # Keep track of generic title as fallback
                if best_title is None:
                    best_title = title

        return best_title

    def _find_most_frequent_title(self, text: str) -> Optional[str]:
        """
        Count occurrences of each known title in the full resume text.
        Returns the most frequent specific (non-generic) title, or the most frequent generic one as fallback.
        """
        title_counts: Dict[str, int] = {}
        for title in self.KNOWN_TITLES:
            pattern = rf"\b{re.escape(title)}\b"
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                title_counts[title] = len(matches)

        if not title_counts:
            return None

        # Prefer the most frequent non-generic title
        specific = {t: c for t, c in title_counts.items() if t not in self._GENERIC_TITLES}
        if specific:
            return max(specific, key=specific.get)  # type: ignore[arg-type]

        # Fallback to most frequent generic title
        return max(title_counts, key=title_counts.get)  # type: ignore[arg-type]

    def _infer_title_from_skills(self, skills: List[str]) -> Optional[str]:
        """
        Infer the most likely role based on the candidate's detected skills.
        Each rule requires a minimum number of matching skills to trigger.
        """
        skill_set = {s.lower() for s in skills}

        best_role: Optional[str] = None
        best_match_count = 0

        for role_skills, min_required, role_name in self._SKILL_ROLE_MAP:
            matched = sum(1 for s in role_skills if s.lower() in skill_set)
            if matched >= min_required and matched > best_match_count:
                best_match_count = matched
                best_role = role_name

        return best_role

    def extract_title(self, text: str, skills: Optional[List[str]] = None) -> Optional[str]:
        """
        Smart title extraction using a 3-tier strategy:
        1. Header Detection — Look for an explicit title in the resume header (top 8 lines).
           If a specific (non-generic) title is found there, trust it immediately.
        2. Frequency Analysis — Count all title mentions across the full resume.
           The most frequently mentioned specific title wins.
        3. Skill-Based Inference — If only generic titles were found (e.g. 'Software Engineer'),
           infer the actual role from the candidate's skill profile.
        """
        # Tier 1: Check the header for an explicit title
        header_title = self._find_title_in_header(text)
        if header_title and header_title not in self._GENERIC_TITLES:
            return header_title

        # Tier 2: Frequency analysis across the full text
        frequent_title = self._find_most_frequent_title(text)
        if frequent_title and frequent_title not in self._GENERIC_TITLES:
            return frequent_title

        # Tier 3: Skill-based inference (replaces generic titles)
        if skills is None:
            skills = self.extract_skills(text)
        inferred = self._infer_title_from_skills(skills)
        if inferred:
            return inferred

        # Final fallback: return whatever title was found (even generic), or None
        return header_title or frequent_title

    def extract_skills(self, text: str) -> List[str]:
        """Identify technology and programming skills present in the resume."""
        found_skills: Set[str] = set()
        for skill in self.KNOWN_SKILLS:
            # Handle special symbols like C++, C#, .NET
            if any(c in skill for c in ["+", "#", "."]):
                escaped = re.escape(skill)
                pattern = rf"(?:^|\s){escaped}(?:$|\s|[,.;])"
            else:
                pattern = rf"\b{re.escape(skill)}\b"

            if re.search(pattern, text, re.IGNORECASE):
                found_skills.add(skill)

        return sorted(list(found_skills), key=lambda s: s.lower())

    MONTH_MAP = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }

    def _calculate_years_from_date_ranges(self, text: str) -> Optional[float]:
        """
        Scan text for date ranges (e.g. '2019 - 2023', 'Jan 2018 - Present', '06/2020 - 12/2022'),
        merge overlapping employment periods, and calculate total career duration.
        """
        now = datetime.now()
        now_year = now.year
        now_month = now.month

        # Match: (Month)? Year to (Month)? (Year | Present | Current | Now | Ongoing)
        date_range_pattern = re.compile(
            r"(?:([a-zA-Z]{3,9}|\d{1,2})[\.,/\s-]+)?(19\d{2}|20\d{2})\s*(?:-|–|—|to)\s*(?:([a-zA-Z]{3,9}|\d{1,2})[\.,/\s-]+)?(19\d{2}|20\d{2}|present|current|now|ongoing)",
            re.IGNORECASE,
        )

        intervals: List[Tuple[float, float]] = []

        def parse_month(val: Optional[str], default: int) -> int:
            if not val:
                return default
            clean = val.strip().lower()
            if clean.isdigit():
                m_int = int(clean)
                return m_int if 1 <= m_int <= 12 else default
            return self.MONTH_MAP.get(clean[:3], default)

        for match in date_range_pattern.finditer(text):
            m1_raw, y1_raw, m2_raw, y2_raw = match.groups()

            start_year = int(y1_raw)
            if start_year < 1970 or start_year > now_year + 1:
                continue

            start_month = parse_month(m1_raw, default=1)
            start_val = start_year + (start_month - 1) / 12.0

            if y2_raw.lower() in ("present", "current", "now", "ongoing"):
                end_val = now_year + now_month / 12.0
            else:
                end_year = int(y2_raw)
                if end_year < start_year or end_year > now_year + 2:
                    continue
                end_month = parse_month(m2_raw, default=12)
                end_val = end_year + end_month / 12.0

            # Discard zero/negative durations or unrealistic single job spans (> 40 years)
            if end_val > start_val and (end_val - start_val) <= 40.0:
                intervals.append((start_val, end_val))

        if not intervals:
            return None

        # Sort and merge overlapping intervals to avoid double-counting concurrent jobs
        intervals.sort(key=lambda x: x[0])
        merged: List[List[float]] = []
        for start, end in intervals:
            if not merged or start > merged[-1][1]:
                merged.append([start, end])
            else:
                merged[-1][1] = max(merged[-1][1], end)

        total_years = sum(end - start for start, end in merged)
        if total_years >= 0.5:
            return round(total_years, 1)

        return None

    def _isolate_work_experience_text(self, text: str) -> str:
        """
        Isolate employment and work history text blocks, excluding Education, Personal Projects,
        Academic Projects, Certifications, and Extracurricular sections so side project dates
        (e.g., 'Aug 2017 - Present' Minecraft project) do not inflate professional work experience.
        """
        lines = text.splitlines()
        filtered_lines = []
        in_work_section = False
        has_seen_work_header = False

        work_headers = {
            "experience", "work experience", "professional experience", "employment",
            "employment history", "work history", "internships", "career history"
        }

        non_work_headers = {
            "education", "academic qualification", "academic qualifications",
            "academic background", "schooling", "academics", "education background",
            "projects", "personal projects", "academic projects", "portfolio",
            "achievements", "certifications", "summary", "profile", "skills",
            "additional", "extracurricular", "extracurriculars", "volunteer"
        }

        for line in lines:
            clean_line = line.strip().lower()
            header_candidate = re.sub(r"^[•\*\-\#\§\ï\s]+", "", clean_line).strip()

            if any(header_candidate.startswith(h) for h in work_headers):
                in_work_section = True
                has_seen_work_header = True
                filtered_lines.append(line)
                continue
            elif in_work_section and any(header_candidate.startswith(h) for h in non_work_headers):
                in_work_section = False

            if in_work_section:
                filtered_lines.append(line)

        # Fallback if no explicit work header was detected: strip out non-work sections
        if not has_seen_work_header or not filtered_lines:
            in_non_work = False
            fallback_lines = []
            for line in lines:
                clean_line = line.strip().lower()
                header_candidate = re.sub(r"^[•\*\-\#\§\ï\s]+", "", clean_line).strip()
                if any(header_candidate.startswith(h) for h in non_work_headers):
                    in_non_work = True
                    continue
                elif in_non_work and any(header_candidate.startswith(h) for h in work_headers):
                    in_non_work = False

                if not in_non_work:
                    fallback_lines.append(line)
            return "\n".join(fallback_lines)

        return "\n".join(filtered_lines)

    def extract_experience_years(self, text: str) -> Optional[float]:
        """
        Enterprise career experience calculation:
        1. Primary (Enterprise Standard): Chronological date range aggregation across isolated work history.
        2. Fallback: Explicit summary declarations ('8+ years of experience') if job history dates are unstated.
        """
        # Primary: Actual verified duration from work history timeline
        work_text = self._isolate_work_experience_text(text)
        calculated_years = self._calculate_years_from_date_ranges(work_text)

        if calculated_years is not None:
            return calculated_years

        # Fallback: Explicit summary declaration if work history dates are missing
        match = re.search(
            r"(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs?)(?:\s+(?:of\s+)?experience)?",
            text,
            re.IGNORECASE,
        )
        if match:
            try:
                val = float(match.group(1))
                if 0.5 <= val <= 50.0:
                    return val
            except ValueError:
                pass

        return None

    def extract_experiences(self, text: str) -> List[Dict[str, Any]]:
        """Extract individual experience entries with dates, title, company, and description."""
        work_text = self._isolate_work_experience_text(text)
        if not work_text.strip():
            return []

        # Find all date matches
        date_range_pattern = re.compile(
            r"(?:([a-zA-Z]{3,9}|\d{1,2})[\.,/\s-]+)?(19\d{2}|20\d{2})\s*(?:-|–|—|to)\s*(?:([a-zA-Z]{3,9}|\d{1,2})[\.,/\s-]+)?(19\d{2}|20\d{2}|present|current|now|ongoing)",
            re.IGNORECASE,
        )

        experiences = []
        lines = [line.strip() for line in work_text.splitlines() if line.strip()]
        
        matches_info = []
        for i, line in enumerate(lines):
            match = date_range_pattern.search(line)
            if match:
                matches_info.append({
                    "line_idx": i,
                    "date_str": match.group(0),
                    "match": match
                })

        for idx, info in enumerate(matches_info):
            line_idx = info["line_idx"]
            
            # The header is usually the line with the date and the line above it
            header_lines = []
            if line_idx > 0 and (idx == 0 or line_idx - 1 > matches_info[idx-1]["line_idx"]):
                header_lines.append(lines[line_idx - 1])
            header_lines.append(lines[line_idx])
            
            header_text = " | ".join(header_lines)
            
            # Attempt to find a known title in the header text
            title = None
            for t in self.KNOWN_TITLES:
                if re.search(rf"\b{re.escape(t)}\b", header_text, re.IGNORECASE):
                    title = t
                    break
            
            # Simple heuristic for company: first word/phrase in header that isn't the date or title
            clean_header = date_range_pattern.sub("", header_text).strip(" |,-")
            if title:
                clean_header = re.sub(rf"\b{re.escape(title)}\b", "", clean_header, flags=re.IGNORECASE).strip(" |,-")
                
            company = clean_header[:100].strip() if clean_header else None
            
            start_desc = line_idx + 1
            end_desc = matches_info[idx+1]["line_idx"] if idx + 1 < len(matches_info) else len(lines)
            
            if idx + 1 < len(matches_info) and end_desc - 1 > start_desc:
                end_desc -= 1

            description_lines = lines[start_desc:end_desc]
            description = "\n".join(description_lines).strip()
            
            start_date = f"{info['match'].group(1) or ''} {info['match'].group(2)}".strip()
            end_date = f"{info['match'].group(3) or ''} {info['match'].group(4)}".strip()
            
            experiences.append({
                "title": title or header_text[:100],
                "company": company,
                "start_date": start_date,
                "end_date": end_date,
                "description": description
            })
            
        return experiences

    # Month names for date matching (supports both full and abbreviated)
    _MONTH_NAMES = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"

    def extract_education(self, text: str) -> List[Dict[str, Any]]:
        """Detect academic degrees, dates, college, and place."""
        found = []

        # Date pattern that supports:
        #   01/2018 - 01/2021          (numeric month)
        #   2018 - 2021                (year only)
        #   July2017–May2020           (word month, no space)
        #   July 2017 – May 2020       (word month, with space)
        #   Jan 2018 - Present         (abbreviated month)
        month_prefix = rf"(?:(?:0?[1-9]|1[0-2])[/\-]|{self._MONTH_NAMES}\s*)"
        year = r"(?:19|20)\d{2}"
        end_part = rf"(?:{month_prefix}?{year}|present|current|now|ongoing)"
        date_pattern = re.compile(
            rf"(?:{month_prefix})?{year}\s*(?:-|–|—|to)\s*{end_part}"
            rf"|(?:{month_prefix})?{year}",
            re.IGNORECASE,
        )
        college_pattern = re.compile(r"\b(?:University|College|Institute|Academy|School|Tech)\b", re.IGNORECASE)

        lines = [line.strip() for line in text.splitlines() if line.strip()]

        for i, line in enumerate(lines):
            for pattern in self.DEGREE_PATTERNS:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    degree_text = line if len(line.split()) < 10 else match.group(0).strip()

                    start_idx = max(0, i - 3)
                    end_idx = min(len(lines), i + 3)
                    context_lines = lines[start_idx:end_idx]

                    # Find the best (longest) date match across context lines
                    date_str = None
                    date_len = 0
                    for ctx_line in context_lines:
                        date_match = date_pattern.search(ctx_line)
                        if date_match:
                            candidate_date = date_match.group(0).strip()
                            if len(candidate_date) > date_len:
                                date_str = candidate_date
                                date_len = len(candidate_date)

                    college_str = None
                    for ctx_line in context_lines:
                        if college_pattern.search(ctx_line):
                            if ctx_line == line:
                                possible_college = ctx_line.replace(match.group(0), "").strip(" ,|-")
                                if college_pattern.search(possible_college):
                                    college_str = possible_college
                                    break
                            else:
                                college_str = ctx_line
                                break

                    found.append({
                        "degree": degree_text,
                        "college": college_str[:100] if college_str else None,
                        "date": date_str,
                        "place": None
                    })
                    break
        return found

    def extract_certifications(self, text: str) -> List[Dict[str, Any]]:
        """Isolate certifications section and extract individual certs."""
        lines = text.splitlines()
        raw_cert_lines: List[str] = []
        in_cert_section = False

        cert_headers = {"certifications", "certificates", "licenses", "certification"}
        non_cert_headers = {
            "education", "academic qualification", "experience", "work experience",
            "employment", "projects", "skills", "summary", "profile", "achievements",
            "interests", "hobbies", "references", "languages", "key achievements",
        }

        # Bullet pattern: lines that start with •, *, -, or similar markers
        bullet_re = re.compile(r"^[•\*\-\#\§\ï]+\s*")

        for line in lines:
            clean_line = line.strip().lower()
            header_candidate = re.sub(r"^[•\*\-\#\§\ï\s]+", "", clean_line).strip()

            if any(header_candidate == h or header_candidate.startswith(h + " ") or header_candidate.startswith(h + "s")
                   for h in cert_headers) and len(header_candidate.split()) < 4:
                in_cert_section = True
                continue
            elif in_cert_section and any(header_candidate.startswith(h) for h in non_cert_headers) and len(header_candidate.split()) < 4:
                in_cert_section = False

            if in_cert_section:
                stripped = line.strip()
                if stripped:
                    is_bullet = bool(bullet_re.match(stripped))
                    clean_cert = bullet_re.sub("", stripped).strip()
                    if clean_cert:
                        if is_bullet or not raw_cert_lines:
                            # New certification entry (bullet line or first line)
                            raw_cert_lines.append(clean_cert)
                        else:
                            # Continuation line (no bullet) — append to previous entry
                            raw_cert_lines[-1] = raw_cert_lines[-1] + " " + clean_cert
                elif raw_cert_lines:
                    # Blank line acts as a separator for non-bullet certs
                    raw_cert_lines.append("")

        # Remove empty trailing markers
        cert_lines = [c for c in raw_cert_lines if c.strip()]

        # Fallback: scan entire document for lines containing "Certified" or "Certification"
        if not cert_lines:
            for line in lines:
                if re.search(r"\b(Certified|Certification)\b", line, re.IGNORECASE) and len(line) < 150:
                    clean_cert = bullet_re.sub("", line.strip()).strip()
                    if clean_cert:
                        cert_lines.append(clean_cert)

        # Now parse each individual cert line into a structured entry
        certs: List[Dict[str, Any]] = []
        date_pattern = re.compile(r"(?:(?:0?[1-9]|1[0-2])[/\-])?(?:19|20)\d{2}", re.IGNORECASE)
        providers = [
            "AWS", "Amazon", "Microsoft", "Azure", "Google", "GCP", "Cisco",
            "Oracle", "CompTIA", "Coursera", "Udemy", "LinkedIn", "Pluralsight",
            "Aspiring Minds", "AspiringMinds", "edX", "Udacity", "HackerRank",
        ]
        # Provider separator patterns: "-Coursera", "– Pluralsight", "- Oracle"
        provider_sep_re = re.compile(
            r"\s*[\-–—]\s*(?:" + "|".join(re.escape(p) for p in providers) + r")\b",
            re.IGNORECASE,
        )

        for cert_line in cert_lines:
            if len(cert_line) < 3:
                continue

            date_match = date_pattern.search(cert_line)
            date_str = date_match.group(0) if date_match else None

            provider_str = None
            for p in providers:
                if re.search(rf"\b{re.escape(p)}\b", cert_line, re.IGNORECASE):
                    provider_str = p
                    break

            # Clean the cert name: remove the provider suffix and date
            name = cert_line
            # Remove provider suffix like "-Coursera" or "– Pluralsight"
            name = provider_sep_re.sub("", name).strip()
            # Remove trailing date
            if date_str:
                name = name.replace(date_str, "").strip(" ,|-–—")
            # Remove trailing separators
            name = re.sub(r"[\-–—,]+$", "", name).strip()

            if not name or len(name) < 3:
                name = cert_line[:150]

            certs.append({
                "name": name[:150],
                "provider": provider_str,
                "date": date_str,
            })

        return certs

    def extract_summary(self, text: str) -> Optional[str]:
        """Extract summary paragraph if present, or first substantive paragraph."""
        paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 40]
        for p in paragraphs:
            lower = p.lower()
            if any(kw in lower for kw in ["summary", "profile", "overview", "experience", "specializing"]):
                return p[:500].strip()
        return paragraphs[0][:500].strip() if paragraphs else None

    def parse_resume_text(self, text: str) -> Dict[str, Any]:
        """
        Orchestrate complete deterministic parsing of resume text.
        Returns a dictionary suitable for CandidateModel instantiation.
        """
        # Extract skills first so we can feed them into smart title inference
        skills = self.extract_skills(text)

        return {
            "full_name": self.extract_name(text),
            "email": self.extract_email(text),
            "phone": self.extract_phone(text),
            "title": self.extract_title(text, skills=skills),
            "skills": skills,
            "experience_years": self.extract_experience_years(text),
            "experiences": self.extract_experiences(text),
            "education": self.extract_education(text),
            "certifications": self.extract_certifications(text),
            "summary": self.extract_summary(text),
            "raw_text": text,
        }

