import pytest
from unittest.mock import patch
from orchestrator import AIOpsOrchestrator

# AIOpsOrchestrator의 무거운 __init__ 과정을 Mocking 합니다.
# 이렇게 하면 LLM 로드나 DB 연결 없이 Orchestrator 객체를 생성할 수 있습니다.
@patch('orchestrator.AssetDataSource')
@patch('orchestrator.MetricDataSource')
@patch('orchestrator.GraphDataSource')
@patch('orchestrator.ManualVectorSource')
@patch('orchestrator.WorkHistoryDataSource')
@patch('orchestrator.ChatHistoryDataSource')
@patch('orchestrator.LlamaIndexManualRetriever')
@patch('orchestrator.MultiSourceRouter')
@patch('orchestrator.ChatOpenAI')
def test_decide_modes(
    MockChatOpenAI, MockMultiSourceRouter, MockLlamaIndexManualRetriever,
    MockChatHistoryDataSource, MockWorkHistoryDataSource, MockManualVectorSource,
    MockGraphDataSource, MockMetricDataSource, MockAssetDataSource
):
    """
    Test the _decide_modes logic in the orchestrator.
    This test runs instantly because heavy initializations are mocked.
    """
    # Mock 객체들 덕분에 __init__은 매우 빠르게 실행됩니다.
    orchestrator = AIOpsOrchestrator()

    # 1. Test for 'config' mode
    query_config = "서버 목록 보여줘"
    modes = orchestrator._decide_modes(query_config)
    assert "config" in modes

    # 2. Test for 'metric' mode
    query_metric = "CPU 사용률 추세 알려줘"
    modes = orchestrator._decide_modes(query_metric)
    assert "metric" in modes

    # 3. Test for 'graph' mode
    query_graph = "a812dpt 장비의 연결 구성도"
    modes = orchestrator._decide_modes(query_graph)
    assert "graph" in modes

    # 4. Test for 'manual' mode
    query_manual = "장애 대응 매뉴얼 찾아줘"
    modes = orchestrator._decide_modes(query_manual)
    assert "manual" in modes
    
    # 5. Test for multiple modes
    query_multi = "was-01 서버의 CPU 사용률과 연결성을 같이 보여줘"
    modes = orchestrator._decide_modes(query_multi)
    assert "config" in modes
    assert "metric" in modes
    assert "graph" in modes

    # 6. Test for default mode when no keywords are matched
    query_default = "안녕?"
    modes = orchestrator._decide_modes(query_default)
    assert "config" in modes
    assert "manual" in modes
