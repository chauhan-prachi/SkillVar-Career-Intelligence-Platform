"""Curated starter taxonomy. It is deliberately small and extensible: it does NOT cover every technology.
Format: slug -> (name, category, aliases, prerequisites, related)."""

CATEGORIES = [("languages", "Programming languages"), ("databases", "Databases & SQL"),
              ("data-engineering", "Data engineering"), ("backend-web", "Backend & web"),
              ("cloud-devops", "Cloud & DevOps"), ("analytics-ml", "Analytics & machine learning"),
              ("cs-fundamentals", "Computer science fundamentals")]

S = {
    # languages
    "python": ("Python", "languages", ["python programming", "python3", "python 3"], [], []),
    "sql": ("SQL", "databases", ["structured query language"], [], []),
    "java": ("Java", "languages", ["java programming", "core java"], [], []),
    "javascript": ("JavaScript", "languages", ["js", "ecmascript", "es6"], [], []),
    "typescript": ("TypeScript", "languages", ["ts"], ["javascript"], []),
    "csharp": ("C#", "languages", ["c sharp"], [], []),
    "cpp": ("C++", "languages", ["cpp"], [], []),
    "golang": ("Golang", "languages", ["go language"], [], []),
    "r-language": ("R programming", "languages", ["r language"], [], []),
    "bash": ("Bash scripting", "languages", ["shell scripting", "bash"], [], ["linux"]),
    # databases
    "sql-joins": ("SQL joins", "databases", ["joins", "join queries"], ["sql"], []),
    "sql-aggregation": ("SQL aggregation", "databases", ["group by", "aggregations", "aggregate functions"], ["sql"], []),
    "sql-window-functions": ("SQL window functions", "databases", ["window functions", "window function", "analytic functions"],
                             ["sql-joins", "sql-aggregation"], []),
    "postgresql": ("PostgreSQL", "databases", ["postgres", "postgresql database", "psql"], ["sql"], ["mysql"]),
    "mysql": ("MySQL", "databases", ["mysql database"], ["sql"], ["postgresql"]),
    "sqlite": ("SQLite", "databases", [], ["sql"], []),
    "mongodb": ("MongoDB", "databases", ["mongo", "mongo db"], [], []),
    "redis": ("Redis", "databases", [], [], []),
    "database-design": ("Database design", "databases", ["schema design", "relational database design"], ["sql"], ["data-modeling"]),
    "data-modeling": ("Data modeling", "databases", ["data modelling", "dimensional modeling", "star schema",
                                                     "entity relationship", "er diagram"], ["database-design"], []),
    "query-optimization": ("Query optimization", "databases", ["query tuning", "sql tuning", "query performance",
                                                               "index tuning", "performance tuning"], ["sql"], []),
    # data engineering
    "etl": ("ETL", "data-engineering", ["elt", "etl pipelines", "extract transform load"], ["python", "sql"], ["data-pipelines"]),
    "data-pipelines": ("Data pipelines", "data-engineering", ["data pipeline", "data ingestion", "batch processing"],
                       ["python", "sql"], ["etl"]),
    "spark": ("Apache Spark", "data-engineering", ["spark", "pyspark"], ["python", "sql"], ["pandas"]),
    "airflow": ("Apache Airflow", "data-engineering", ["airflow"], ["python", "data-pipelines"], []),
    "kafka": ("Apache Kafka", "data-engineering", ["kafka"], ["data-pipelines"], []),
    "dbt": ("dbt", "data-engineering", ["data build tool"], ["sql"], []),
    "data-warehousing": ("Data warehousing", "data-engineering", ["data warehouse", "data warehouses", "dwh"], ["data-modeling"], []),
    "data-quality": ("Data quality", "data-engineering", ["data validation", "data quality checks", "great expectations"], ["sql"], []),
    "pandas": ("Pandas", "data-engineering", ["pandas library"], ["python"], ["numpy"]),
    "numpy": ("NumPy", "data-engineering", [], ["python"], ["pandas"]),
    # backend & web
    "django": ("Django", "backend-web", ["django framework"], ["python"], ["flask", "fastapi"]),
    "flask": ("Flask", "backend-web", [], ["python"], ["django", "fastapi"]),
    "fastapi": ("FastAPI", "backend-web", [], ["python", "rest-apis"], ["django", "flask"]),
    "rest-apis": ("REST APIs", "backend-web", ["rest api", "restful api", "restful apis", "restful services", "web apis"], [], []),
    "nodejs": ("Node.js", "backend-web", ["nodejs", "node js"], ["javascript"], []),
    "html": ("HTML", "backend-web", ["html5"], [], ["css"]),
    "css": ("CSS", "backend-web", ["css3"], [], ["html"]),
    "react": ("React", "backend-web", ["reactjs", "react.js"], ["javascript", "html", "css"], []),
    # cloud & devops
    "git": ("Git", "cloud-devops", ["github", "gitlab", "version control"], [], []),
    "docker": ("Docker", "cloud-devops", ["containers", "containerization", "dockerfile"], ["linux"], ["kubernetes"]),
    "kubernetes": ("Kubernetes", "cloud-devops", ["k8s"], ["docker"], ["docker"]),
    "aws": ("AWS", "cloud-devops", ["amazon web services"], [], ["azure", "gcp"]),
    "azure": ("Microsoft Azure", "cloud-devops", ["azure cloud"], [], ["aws", "gcp"]),
    "gcp": ("Google Cloud Platform", "cloud-devops", ["google cloud", "gcp"], [], ["aws", "azure"]),
    "ci-cd": ("CI/CD", "cloud-devops", ["continuous integration", "continuous delivery", "github actions", "jenkins"], ["git"], []),
    "linux": ("Linux", "cloud-devops", ["unix"], [], []),
    # analytics & ML
    "statistics": ("Statistics", "analytics-ml", ["statistical analysis", "hypothesis testing"], [], []),
    "data-analysis": ("Data analysis", "analytics-ml", ["data analytics", "exploratory data analysis", "eda"], ["sql"], []),
    "data-visualization": ("Data visualization", "analytics-ml", ["data visualisation", "dashboards", "dashboarding"],
                           ["data-analysis"], []),
    "tableau": ("Tableau", "analytics-ml", [], ["data-visualization"], ["power-bi"]),
    "power-bi": ("Power BI", "analytics-ml", ["powerbi"], ["data-visualization"], ["tableau"]),
    "excel": ("Excel", "analytics-ml", ["microsoft excel", "spreadsheets"], [], []),
    "scikit-learn": ("scikit-learn", "analytics-ml", ["sklearn"], ["python", "statistics"], []),
    "machine-learning": ("Machine learning", "analytics-ml", ["ml", "machine learning models"], ["statistics", "python"], []),
    # CS fundamentals
    "data-structures": ("Data structures", "cs-fundamentals", ["data structure", "dsa"], [], []),
    "algorithms": ("Algorithms", "cs-fundamentals", ["algorithm design"], ["data-structures"], []),
    "oop": ("Object-oriented programming", "cs-fundamentals", ["oop", "object oriented design"], [], []),
    "unit-testing": ("Unit testing", "cs-fundamentals", ["pytest", "unittest", "test driven development", "tdd",
                                                          "automated testing"], [], []),
    "software-design": ("Software design", "cs-fundamentals", ["system design", "design patterns"], ["oop"], []),
    "agile": ("Agile", "cs-fundamentals", ["scrum", "kanban"], [], []),
}

# role slug -> (title, description, [(skill, importance, required?)])
ROLES = {
    "junior-data-engineer": ("Junior Data Engineer", "Builds and maintains reliable data pipelines.", [
        ("sql", 1.0, True), ("sql-joins", 0.8, True), ("sql-aggregation", 0.8, True), ("python", 1.0, True),
        ("etl", 0.9, True), ("data-pipelines", 0.8, True), ("data-modeling", 0.7, True), ("data-quality", 0.6, True),
        ("pandas", 0.7, True), ("git", 0.5, True), ("postgresql", 0.6, True), ("sql-window-functions", 0.5, False),
        ("query-optimization", 0.5, False), ("unit-testing", 0.5, False), ("airflow", 0.5, False),
        ("docker", 0.3, False), ("linux", 0.3, False)]),
    "data-analyst": ("Data Analyst", "Turns data into decisions with SQL, statistics and visualization.", [
        ("sql", 1.0, True), ("sql-joins", 0.7, True), ("sql-aggregation", 0.8, True), ("data-analysis", 1.0, True),
        ("statistics", 0.7, True), ("data-visualization", 0.8, True), ("excel", 0.7, True), ("python", 0.6, False),
        ("pandas", 0.6, False), ("tableau", 0.4, False), ("power-bi", 0.4, False)]),
    "python-backend-developer": ("Python Backend Developer", "Builds server-side applications and APIs in Python.", [
        ("python", 1.0, True), ("rest-apis", 0.9, True), ("sql", 0.8, True), ("django", 0.7, True), ("oop", 0.6, True),
        ("unit-testing", 0.7, True), ("git", 0.6, True), ("data-structures", 0.5, True), ("postgresql", 0.6, False),
        ("docker", 0.4, False), ("ci-cd", 0.4, False)]),
}
