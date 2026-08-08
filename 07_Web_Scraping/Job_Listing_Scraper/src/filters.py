from __future__ import annotations

from src.utils import (
    contains_keyword,
)


class JobFilter:

    def filter(
        self,
        jobs,
        keyword="",
        location="",
    ):

        filtered_jobs = []

        for job in jobs:

            title = job.get(
                "title",
                "",
            )

            company = job.get(
                "company",
                "",
            )

            job_location = job.get(
                "location",
                "",
            )

            title_match = contains_keyword(
                title,
                keyword,
            )

            company_match = contains_keyword(
                company,
                keyword,
            )

            location_match = contains_keyword(
                job_location,
                location,
            )

            if keyword:

                keyword_match = title_match or company_match

            else:

                keyword_match = True

            if keyword_match and location_match:

                filtered_jobs.append(job)

        return filtered_jobs

    def filter_by_keyword(
        self,
        jobs,
        keyword,
    ):

        return self.filter(
            jobs,
            keyword=keyword,
        )

    def filter_by_location(
        self,
        jobs,
        location,
    ):

        return self.filter(
            jobs,
            location=location,
        )
