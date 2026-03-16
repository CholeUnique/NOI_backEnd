import pytest


def test_get_neo4j_driver_returns_none_when_unconfigured(monkeypatch):
    from app.neo4j import close_neo4j_driver, get_neo4j_driver

    close_neo4j_driver()
    monkeypatch.delenv("NEO4J_URI", raising=False)
    monkeypatch.delenv("NEO4J_USER", raising=False)
    monkeypatch.delenv("NEO4J_USERNAME", raising=False)
    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
    monkeypatch.delenv("NEO4J_DATABASE", raising=False)

    assert get_neo4j_driver() is None


def test_behavior_graph_builder_requires_neo4j_when_store_is_neo4j(db_session, monkeypatch):
    monkeypatch.setenv("BEHAVIOR_GRAPH_STORE", "neo4j")
    monkeypatch.delenv("NEO4J_URI", raising=False)
    monkeypatch.delenv("NEO4J_USER", raising=False)
    monkeypatch.delenv("NEO4J_USERNAME", raising=False)
    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
    monkeypatch.delenv("NEO4J_DATABASE", raising=False)

    from app.services.profile.behavior_graph import BehaviorGraphBuilder

    builder = BehaviorGraphBuilder(db_session, user_id=1)
    with pytest.raises(RuntimeError, match="Neo4j 未配置或不可用"):
        builder.get_graph_stats()

