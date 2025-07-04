from pydantic import BaseModel, Field
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
    active: Optional[bool] = None
    keywords: List[str] = Field(default_factory=list)
    matchDescription: Optional[bool] = None
    matchSkills: Optional[bool] = None
    matchTitle: Optional[bool] = None

class AgencyStats(BaseModel):
    sent: int
    viewed: int
    accepted: int
    hired: int
    conversionRate: Optional[float] = None

class BudgetPrefs(BaseModel):
    allowUnspecifiedBudget: Optional[bool] = None
    avgHourlyRate: Optional[dict] = None
    hourlyRate: Optional[dict] = None
    connectsPrice: Optional[dict] = None
    fixedPrice: Optional[dict] = None
    jobDurations: List[str] = Field(default_factory=list)
    hourlyWorkloads: List[str] = Field(default_factory=list)
    noAvgHourlyRatePaid: Optional[bool] = None
    noHireRate: Optional[bool] = None
    minClientHireRate: Optional[int] = None
    onlyContractToHire: Optional[bool] = None

class ClientPrefs(BaseModel):
    companySizeRange: List[str] = Field(default_factory=list)
    descriptionLanguage: Optional[dict] = None
    excludeCountryCodes: List[dict] = Field(default_factory=list)
    excludeIndustry: List[str] = Field(default_factory=list)
    hireHistory: List[str] = Field(default_factory=list)
    includeCountryCodes: List[dict] = Field(default_factory=list)
    includeIndustry: List[str] = Field(default_factory=list)
    includeWithNoFeedback: Optional[bool] = None
    maxTotalSpent: Optional[int] = None
    minFeedbackScore: Optional[str] = None
    minTotalSpent: Optional[int] = None
    paymentMethodVerified: Optional[bool] = None
    phoneNumberVerified: Optional[bool] = None
    timezones: List[str] = Field(default_factory=list)

class VendorPrefs(BaseModel):
    englishProficiency: Optional[str] = None
    excludeWithQuestions: Optional[bool] = None
    experienceLevel: List[str] = Field(default_factory=list)
    includeCountryCodes: List[dict] = Field(default_factory=list)
    includeFeatured: Optional[bool] = None
    includeWithoutCountryPreference: Optional[bool] = None
    languages: List[str] = Field(default_factory=list)
    minGetmanyJobScore: Optional[float] = None
    type: List[str] = Field(default_factory=list)

class SearchConfig(BaseModel):
    jobCategories: List[str] = Field(default_factory=list)
    excludeKeywords: Optional[Keywords] = None
    includeKeywords: Optional[Keywords] = None
    budgetPrefs: Optional[BudgetPrefs] = None
    client: Optional[ClientPrefs] = None
    vendor: Optional[VendorPrefs] = None

class CreateJobSearchRequest(BaseModel):
    name: str
    searchConfig: SearchConfig
