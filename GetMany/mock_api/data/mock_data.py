# In-memory storage for created job searches
job_searches_db = {}

agency_details = {
    "data": {
        "uid": "23b1f7fa-a3bc-41dd-9b89-301d8d9c8d50",
        "name": "PixelPioneers Studio",
        "description": "A creative studio specializing in digital experiences.",
        "timezone": "Europe/Kyiv",
        "connectsBalance": 324
    }
}

agency_stats = {
    "sent": 150,
    "viewed": 42,
    "accepted": 18,
    "hired": 7
}

job_candidates = [
    {
        "uid": "job_12345",
        "title": "Senior Frontend Developer (React)",
        "description": "We are looking for an experienced frontend developer to join our team...",
        "createdAt": "2025-07-04T10:00:00Z",
        "skills": ["react", "typescript", "javascript"],
        "externalLink": "https://www.upwork.com/jobs/12345",
        "budget": {"hourlyRate": {"min": 50, "max": 75}},
        "applicationCost": 16,
        "featured": True,
        "category": "Web Development",
        "ciphertext": "...",
        "getmanyJobScore": 4.8,
        "client": {"country_code": "US", "timezone": "America/New_York"}
    },
    {
        "uid": "job_67890",
        "title": "Backend Python Engineer",
        "description": "Seeking a skilled Python developer for a long-term project...",
        "createdAt": "2025-07-03T18:30:00Z",
        "skills": ["python", "django", "postgres"],
        "externalLink": "https://www.upwork.com/jobs/67890",
        "budget": {"fixedBudget": 5000},
        "applicationCost": 12,
        "featured": False,
        "category": "Web Development",
        "ciphertext": "...",
        "getmanyJobScore": 4.5,
        "client": {"country_code": "GB", "timezone": "Europe/London"}
    }
]

agency_proposals = [
    {
        "id": "prop_abcde",
        "job_title": "Design a new mobile app UI",
        "client_name": "Innovate Inc.",
        "submitted_at": "2025-07-01T11:00:00Z",
        "status": "viewed"
    },
    {
        "id": "prop_fghij",
        "job_title": "Build a responsive e-commerce website",
        "client_name": "Shopify Plus Experts",
        "submitted_at": "2025-06-28T15:45:00Z",
        "status": "accepted"
    }
]
