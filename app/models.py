from datetime import date, datetime

from sqlalchemy import JSON, CheckConstraint, Column
from sqlmodel import Field, Relationship, SQLModel


def now_local() -> datetime:
    """Local PC wall-clock time; SQLite stores naive datetimes consistently."""
    return datetime.now()


class ClientFields(SQLModel):
    name: str
    gender: str | None = None
    birth_date: date | None = None
    postal_code: str | None = None
    address: str | None = None
    phone: str | None = None
    mobile_phone: str | None = None


class AssessmentFields(SQLModel):
    received_date: date | None = None
    assessor_name: str | None = None
    office_name: str | None = None
    family_request: str | None = None
    family_structure_text: str | None = None
    living_status: str | None = None
    medical_history: str | None = None
    primary_doctor: str | None = None
    medication_status: str | None = None
    adl_independence_level: str | None = None
    dementia_independence_level: str | None = None
    care_application_status: str | None = None
    care_level: str | None = None
    certification_date: date | None = None
    certification_valid_from: date | None = None
    certification_valid_to: date | None = None
    assessment_reason: str | None = None
    assessment_analysis_result: str | None = None
    disability_certificate_present: bool | None = None
    disability_certificate_type: str | None = None
    disability_certificate_grade: str | None = None
    current_services: str | None = None


class CheckFields(SQLModel):
    health_status: str | None = None
    adl: str | None = None
    iadl: str | None = None
    cognition: str | None = None
    communication: str | None = None
    social_relationship: str | None = None
    elimination: str | None = None
    skin: str | None = None
    oral_hygiene: str | None = None
    nutrition: str | None = None
    behavior: str | None = None
    caregiving_capacity: str | None = None
    home_environment: str | None = None
    special_conditions: str | None = None


class Client(ClientFields, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=now_local)
    updated_at: datetime = Field(default_factory=now_local)
    emergency_contacts: list["EmergencyContact"] = Relationship(back_populates="client")
    assessments: list["Assessment"] = Relationship(back_populates="client")


class EmergencyContact(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    client_id: int = Field(foreign_key="client.id", index=True)
    name: str | None = None
    relationship: str | None = None
    phone: str | None = None
    mobile: str | None = None
    address: str | None = None
    priority: int | None = None
    client: Client = Relationship(back_populates="emergency_contacts")


class Assessment(AssessmentFields, table=True):
    __table_args__ = (CheckConstraint("source_assessment_id IS NULL OR source_assessment_id != id"),)

    id: int | None = Field(default=None, primary_key=True)
    client_id: int = Field(foreign_key="client.id", index=True)
    source_assessment_id: int | None = Field(default=None, foreign_key="assessment.id", index=True)
    client_snapshot: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=now_local, index=True)
    updated_at: datetime = Field(default_factory=now_local)
    client: Client = Relationship(back_populates="assessments")
    check: "AssessmentCheck" = Relationship(back_populates="assessment", sa_relationship_kwargs={"uselist": False})
    source_assessment: "Assessment" = Relationship(
        back_populates="reassessments", sa_relationship_kwargs={"remote_side": "Assessment.id"},
    )
    reassessments: list["Assessment"] = Relationship(back_populates="source_assessment")


class AssessmentCheck(CheckFields, table=True):
    id: int | None = Field(default=None, primary_key=True)
    assessment_id: int = Field(foreign_key="assessment.id", unique=True, index=True)
    assessment: Assessment = Relationship(back_populates="check")
