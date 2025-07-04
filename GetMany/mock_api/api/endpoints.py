from fastapi import APIRouter, Depends
from typing import Optional
import datetime
import uuid

from models.models import (
    SearchConfig,
    CreateJobSearchRequest,
    AgencyStats,
    DateRangeParams,
    JobFeedParams
)
from data import mock_data

router = APIRouter()

@router.get("/agency")
def get_agency():
    return mock_data.agency_details

@router.get("/agency/stats", response_model=dict)
def get_agency_stats(params: DateRangeParams = Depends()):
    stats_data = mock_data.agency_stats.copy()
    stats = AgencyStats(**stats_data)

    if params.include == "conversion_rate" and stats.sent > 0:
        stats.conversionRate = round((stats.hired / stats.sent) * 100, 2)
    
    return {"data": stats.model_dump(exclude_none=True)}

@router.get("/job-searches/{id}/feed", response_model=dict)
def get_job_searches_by_id_feed(id: str, params: JobFeedParams = Depends()):
    """This endpoint mocks the 'Search job candidates' functionality."""
    # The mock implementation doesn't use the params yet, but the signature is correct.
    return {"data": mock_data.job_candidates}

@router.get("/agency/proposals", response_model=dict)
def get_agency_proposals():
    """This is a new mock endpoint to pull agency proposals."""
    return {"data": mock_data.agency_proposals}

@router.post("/job-searches", status_code=201)
def create_job_search(search_request: CreateJobSearchRequest):
    search_id = str(uuid.uuid4())
    new_search = {
        "id": search_id,
        "name": search_request.name,
        "updatedAt": datetime.datetime.now().isoformat(),
        "bidder": {"status": "not_configured", "mode": None},
        "searchConfig": search_request.searchConfig.model_dump()
    }
    mock_data.job_searches_db[search_id] = new_search
    return {"data": new_search}

@router.post("/job-searches/sample")
def get_job_search_sample(search_config: SearchConfig):
    """Mocks getting a sample of jobs for a given search configuration."""
    sample_jobs = get_job_searches_by_id_feed(id="sample", params=JobFeedParams())
    return {
        "count": len(sample_jobs["data"]),
        "data": sample_jobs["data"]
    }
