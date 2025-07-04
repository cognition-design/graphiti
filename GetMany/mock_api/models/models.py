from pydantic import BaseModel
from typing import List, Optional
import datetime

class JobFeedBudget(BaseModel):
    fixedBudget: Optional[float] = None
    hourlyRate: Optional[dict] = None

class JobFeedClient(BaseModel):
    country_code: str
    timezone: str

class JobFeedItem(BaseModel):
    uid: str
    title: str
    description: str
    createdAt: datetime.datetime
    skills: List[str]
    externalLink: str
    budget: Optional[JobFeedBudget] = None
    applicationCost: int
    featured: bool
    category: str
    ciphertext: str
    getmanyJobScore: float
    client: JobFeedClient

class Proposal(BaseModel):
    id: str
    job_title: str
    client_name: str
    submitted_at: datetime.datetime
    status: str

class Keywords(BaseModel):
    active: bool
    keywords: List[str]
    matchDescription: bool
    matchSkills: bool
    matchTitle: bool

class BudgetPrefs(BaseModel):
    allowUnspecifiedBudget: bool
    avgHourlyRate: Optional[dict] = None
    hourlyRate: Optional[dict] = None
    connectsPrice: Optional[dict] = None
    fixedPrice: Optional[dict] = None
    jobDurations: List[str]
    hourlyWorkloads: List[str]
    noAvgHourlyRatePaid: bool
    noHireRate: bool
    minClientHireRate: int
    onlyContractToHire: bool

class ClientPrefs(BaseModel):
    companySizeRange: List[str]
    descriptionLanguage: dict
    excludeCountryCodes: List[dict]
    excludeIndustry: List[str]
    hireHistory: List[str]
    includeCountryCodes: List[dict]
    includeIndustry: List[str]
    includeWithNoFeedback: bool
    maxTotalSpent: int
    minFeedbackScore: str
    minTotalSpent: int
    paymentMethodVerified: bool
    phoneNumberVerified: bool
    timezones: List[str]

class VendorPrefs(BaseModel):
    englishProficiency: str
    excludeWithQuestions: bool
    experienceLevel: List[str]
    includeCountryCodes: List[dict]
    includeFeatured: bool
    includeWithoutCountryPreference: bool
    languages: List[str]
    minGetmanyJobScore: float
    type: List[str]

class SearchConfig(BaseModel):
    jobCategories: List[str]
    excludeKeywords: Keywords
    includeKeywords: Keywords
    budgetPrefs: Optional[BudgetPrefs] = None
    client: Optional[ClientPrefs] = None
    vendor: Optional[VendorPrefs] = None

class CreateJobSearchRequest(BaseModel):
    name: str
    searchConfig: SearchConfig
