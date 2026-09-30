"""friday · integrations/jobs_api.py

HTTP surface for the Jobs command center (/api/v1/jobs/*), registered into the
dashboard server's GET/POST tables. Bad input raises ValueError -> 400.
"""

from integrations import jobs, jobs_actions


def _n(body: dict) -> int:
    try:
        return int(body.get("n"))
    except (TypeError, ValueError):
        raise ValueError("missing role number n") from None


def overview(_body: dict) -> dict:
    return jobs.overview()


def batch(body: dict) -> dict:
    name = jobs.check_batch(body.get("batch") or jobs.overview()["latest"])
    items = jobs.roles(name)
    return {"batch": name, "roles": items, "summary": jobs.summarize(items),
            "progress": jobs.progress(name)}


def decide(body: dict) -> dict:
    entry = jobs_actions.decide(str(body.get("batch", "")), _n(body),
                                str(body.get("decision", "")))
    return {"ok": True, "entry": entry}


def answer(body: dict) -> dict:
    entry = jobs_actions.answer(str(body.get("batch", "")), _n(body),
                                str(body.get("question", "")), str(body.get("text", "")))
    return {"ok": True, "entry": entry}


def open_file(body: dict) -> dict:
    message = jobs_actions.open_file(str(body.get("batch", "")), _n(body),
                                     str(body.get("which", "")))
    return {"ok": True, "message": message}


GET_API = {"/api/v1/jobs/overview": overview}
POST_API = {
    "/api/v1/jobs/batch": batch,
    "/api/v1/jobs/decide": decide,
    "/api/v1/jobs/answer": answer,
    "/api/v1/jobs/open": open_file,
}
