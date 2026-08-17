import uuid

from app.services.research_memory import (
    ResearchFinding,
    ResearchMemoryService,
    ResearchNote,
    SavedSource,
)


def test_save_and_retrieve_findings() -> None:
    svc = ResearchMemoryService()
    p1 = str(uuid.uuid4())

    f = ResearchFinding(
        project_id=p1,
        statement="ResNet-50 outperforms baseline ResNet-34 on ImageNet by 2.1%.",
        source_ids=["S1"],
    )

    svc.save_finding(f)
    retrieved = svc.get_findings(p1)

    assert len(retrieved) == 1
    assert retrieved[0].statement == f.statement


def test_project_isolation() -> None:
    svc = ResearchMemoryService()
    p1 = str(uuid.uuid4())
    p2 = str(uuid.uuid4())

    f = ResearchFinding(project_id=p1, statement="Finding for P1")
    svc.save_finding(f)

    res_p1 = svc.get_findings(p1)
    res_p2 = svc.get_findings(p2)

    assert len(res_p1) == 1
    assert len(res_p2) == 0


def test_delete_finding() -> None:
    svc = ResearchMemoryService()
    p1 = str(uuid.uuid4())

    f = ResearchFinding(project_id=p1, statement="Temporary finding")
    svc.save_finding(f)

    deleted = svc.delete_finding(p1, f.id)
    assert deleted is True

    retrieved = svc.get_findings(p1)
    assert len(retrieved) == 0


def test_save_and_retrieve_notes_and_sources() -> None:
    svc = ResearchMemoryService()
    p1 = str(uuid.uuid4())

    n = ResearchNote(project_id=p1, title="Methodology Note", content="Focus on section 4 results.")
    s = SavedSource(project_id=p1, document_id=str(uuid.uuid4()), filename="paper.pdf", excerpt="Key excerpt text.")

    svc.save_note(n)
    svc.save_source(s)

    notes = svc.get_notes(p1)
    sources = svc.get_sources(p1)

    assert len(notes) == 1
    assert len(sources) == 1
    assert notes[0].title == "Methodology Note"


def test_build_memory_context() -> None:
    svc = ResearchMemoryService()
    p1 = str(uuid.uuid4())

    f = ResearchFinding(project_id=p1, statement="ResNet-50 achieves 93.4% accuracy.")
    svc.save_finding(f)

    ctx = svc.build_memory_context(p1, "What accuracy does ResNet-50 achieve?")
    assert "PERSISTENT WORKSPACE MEMORY" in ctx
    assert "93.4% accuracy" in ctx
