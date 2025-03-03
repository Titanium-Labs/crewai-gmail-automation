from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

class DateCalculationSchema(BaseModel):
    """Schema for DateCalculationTool input."""
    email_date: str = Field(..., description="Email date in ISO format (YYYY-MM-DD)")
    reference_date: Optional[str] = Field(None, description="Reference date in ISO format (YYYY-MM-DD). Defaults to today.")

class DateCalculationTool(BaseTool):
    """Tool to calculate the age of an email in days."""
    name: str = "calculate_email_age"
    description: str = "Calculates the age of an email in days based on its date"
    args_schema: type[BaseModel] = DateCalculationSchema

    def _run(self, email_date: str, reference_date: Optional[str] = None) -> str:
        """
        Calculate the age of an email in days.
        
        Args:
            email_date: The date of the email in ISO format (YYYY-MM-DD)
            reference_date: Optional reference date in ISO format (YYYY-MM-DD). Defaults to today.
            
        Returns:
            A string with the age in days and whether it meets various age thresholds.
        """
        try:
            # Handle empty or invalid date
            if not email_date or email_date == "":
                return "Error: Email date is empty or invalid. Cannot calculate age."
            
            # Get today's date automatically
            today = datetime.now().strftime("%Y-%m-%d")
            
            # Parse the email date
            try:
                email_datetime = datetime.strptime(email_date, "%Y-%m-%d")
            except ValueError:
                return f"Error: Could not parse email date '{email_date}'. Format should be YYYY-MM-DD."
            
            # Get reference date (today if not provided)
            if reference_date:
                try:
                    ref_datetime = datetime.strptime(reference_date, "%Y-%m-%d")
                except ValueError:
                    # If reference_date is invalid, use today
                    ref_datetime = datetime.strptime(today, "%Y-%m-%d")
            else:
                ref_datetime = datetime.strptime(today, "%Y-%m-%d")
            
            # Calculate age in days
            age_days = (ref_datetime - email_datetime).days
            
            # Check against common thresholds
            result = f"Email age: {age_days} days\n"
            result += f"Today's date: {today}\n"
            result += f"Email date: {email_date}\n"
            result += f"- Less than 5 days old: {'Yes' if age_days < 5 else 'No'}\n"
            result += f"- Older than 7 days: {'Yes' if age_days > 7 else 'No'}\n"
            result += f"- Older than 10 days: {'Yes' if age_days > 10 else 'No'}\n"
            result += f"- Older than 14 days: {'Yes' if age_days > 14 else 'No'}\n"
            result += f"- Older than 30 days: {'Yes' if age_days > 30 else 'No'}\n"
            
            return result
            
        except Exception as e:
            return f"Error calculating email age: {e}" 