"""
Enterprise Compliance Docket Schema for FinReg-SLM.

Defines Pydantic data structures for audit-ready compliance determinations,
statutory citation registries, actionable filing checklists, and penal exposure ratings.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class StatutoryCitation(BaseModel):
    regulator: str = Field(description="Issuing regulatory body (e.g., RBI, SEBI, CBIC, MCA, IBBI)")
    circular_id: str = Field(description="Official circular or notification reference (e.g., RBI/2023-24/102)")
    provision_clause: str = Field(description="Specific section, paragraph, or clause path")
    effective_status: str = Field(default="ACTIVE", description="Current legal status (ACTIVE, SUPERSEDED, AMENDED)")
    statutory_title: Optional[str] = Field(default=None, description="Official title of the regulatory circular")

class ComplianceActionItem(BaseModel):
    step_number: int = Field(description="Sequential order of statutory action")
    action_description: str = Field(description="Clear mandatory task required for compliance")
    statutory_deadline: Optional[str] = Field(default=None, description="Filing or implementation timeline")
    prescribed_form: Optional[str] = Field(default=None, description="Statutory form or reporting portal (e.g., Form FC-GPR, PAS-3)")

class EnterpriseComplianceDocket(BaseModel):
    query_id: Optional[str] = Field(default=None, description="Unique inquiry identifier")
    as_of_date: str = Field(description="Jurisdictional as-of date evaluated")
    determination: str = Field(
        description="Statutory determination: COMPLIANT | NON_COMPLIANT | PERMITTED_WITH_CONDITIONS | STATUTORY_BARRED | INSUFFICIENT_CORPUS_EVIDENCE"
    )
    executive_summary: str = Field(description="Concise 2-3 sentence legal determination")
    governing_citations: List[StatutoryCitation] = Field(default_factory=list, description="Verifiable statutory provisions relied upon")
    actionable_checklist: List[ComplianceActionItem] = Field(default_factory=list, description="Mandatory operational and filing steps")
    penal_liability_rating: Optional[str] = Field(default=None, description="Penal exposure, monetary fines, or compounding provisions")
    calculated_metrics: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Deterministic financial values computed via REPL")
    audit_confidence_score: float = Field(default=1.0, description="Verification confidence score between 0.0 and 1.0")

if __name__ == "__main__":
    sample = EnterpriseComplianceDocket(
        as_of_date="2026-06-01",
        determination="PERMITTED_WITH_CONDITIONS",
        executive_summary="Foreign direct investment under the automatic route is permitted up to 100% in single-brand retail trading, subject to 30% local sourcing requirements within 5 years of commercial operations.",
        governing_citations=[
            StatutoryCitation(
                regulator="RBI",
                circular_id="RBI/FED/2017-18/15",
                provision_clause="Master Direction on Foreign Investment / Section 4.2",
                effective_status="ACTIVE"
            )
        ],
        actionable_checklist=[
            ComplianceActionItem(
                step_number=1,
                action_description="File Form FC-GPR via FIRMS portal within 30 days of equity allotment.",
                prescribed_form="Form FC-GPR",
                statutory_deadline="30 days from allotment"
            )
        ],
        penal_liability_rating="Non-compliance attracts Section 13 FEMA 1999 penalty up to thrice the sum involved.",
        calculated_metrics={"crar": "12.5%", "local_sourcing_target": "30%"}
    )
    print("Schema Validation Success:")
    print(sample.model_dump_json(indent=2))
