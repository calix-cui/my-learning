"""known-failures.txt 不能烂：每条都要还指向真实存在的用例。

表是给「环境跑不过、但代码没问题」用的。用例改名或删除后如果没人清理，
表就会越积越旧，直到新失败被它挡住。
"""

from pathlib import Path

import pytest

from tests.conftest import known_failure_ids

TESTS_DIR = Path(__file__).parent


@pytest.mark.parametrize("node_id", sorted(known_failure_ids()))
def test_entry_points_at_a_real_test(node_id: str) -> None:
    path, _, name = node_id.partition("::")
    assert name, f"{node_id} 少了用例名"
    module = TESTS_DIR.parent / path
    assert module.is_file(), f"{node_id} 指向的文件不存在：{module}"
    function = name.split("[")[0]
    assert function in module.read_text(encoding="utf-8"), (
        f"{node_id} 指向的用例已经不在 {path} 里，请从 known-failures.txt 删掉这一行"
    )
