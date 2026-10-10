from jobhunter.models import Job


def _job(**kw):
    base = dict(source="greenhouse", external_id="1", company="Acme", title="Engineer", url="u")
    return Job(**(base | kw))


def test_content_hash_is_stable_and_changes_with_content():
    a = _job(description="python")
    assert a.content_hash == _job(description="python").content_hash
    assert a.content_hash != _job(description="go").content_hash


def test_defaults():
    job = _job()
    assert job.remote == "unknown"
    assert job.salary_min is None
