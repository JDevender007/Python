from __future__ import annotations

from bs4 import BeautifulSoup

from src.utils import (
    build_absolute_url,
    clean_text,
)


class JobParser:

    def parse(
        self,
        html,
        base_url,
        limit=100,
    ):

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        jobs = []

        job_elements = soup.select("tr.job")

        if not job_elements:

            job_elements = soup.select("article")

        if not job_elements:

            job_elements = soup.select(".job")

        for element in job_elements:

            job = self.parse_job(
                element,
                base_url,
            )

            if job:

                jobs.append(job)

            if len(jobs) >= limit:

                break

        return jobs

    def parse_job(
        self,
        element,
        base_url,
    ):

        title_element = element.select_one(".position")

        if not title_element:

            title_element = element.select_one(".jobtitle")

        if not title_element:

            title_element = element.select_one("h2")

        if not title_element:

            title_element = element.select_one("h3")

        if not title_element:

            return None

        title = clean_text(title_element.get_text())

        company_element = element.select_one(".company")

        if not company_element:

            company_element = element.select_one(".companyLink")

        company = ""

        if company_element:

            company = clean_text(company_element.get_text())

        location_element = element.select_one(".location")

        if not location_element:

            location_element = element.select_one(".locationLink")

        location = ""

        if location_element:

            location = clean_text(location_element.get_text())

        link_element = element.select_one("a[href]")

        link = ""

        if link_element:

            link = build_absolute_url(
                base_url,
                link_element.get("href"),
            )

        description_element = element.select_one(".description")

        description = ""

        if description_element:

            description = clean_text(description_element.get_text())

        return {
            "title": title,
            "company": company,
            "location": location,
            "description": description,
            "link": link,
        }
