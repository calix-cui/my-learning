"""四则运算工具：用 `ast` 白名单解析，不用 `eval`。

为什么要专门处理 `^`：实测 DeepSeek 会把「3 的 5 次方」写成 `3^5`，
而 Python 里 `^` 是按位异或（3 XOR 5 = 6）。数学语境下 `^` 就是幂，
这里先做替换，避免给模型一个反直觉的错结果。
"""

import ast
import operator
from typing import Any

from pydantic import BaseModel, Field

from app.agent.tools.base import ToolError

MAX_EXPRESSION_LENGTH = 200

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


class CalculatorArgs(BaseModel):
    expression: str = Field(
        min_length=1,
        max_length=MAX_EXPRESSION_LENGTH,
        description="算术表达式，支持 + - * / // % 与 ** 或 ^ 表示的幂，例如 (12+8)*3 或 3**5",
    )


def evaluate(expression: str) -> float | int:
    """解析并求值；只允许数字、括号与上述运算符。"""
    text = expression.strip().replace("^", "**")
    if not text:
        raise ToolError("表达式不能为空")
    if len(text) > MAX_EXPRESSION_LENGTH:
        raise ToolError("表达式太长")

    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as exc:
        raise ToolError("表达式语法不正确") from exc

    try:
        value = _eval_node(tree.body)
    except ZeroDivisionError as exc:
        raise ToolError("不能除以零") from exc
    except OverflowError as exc:
        raise ToolError("结果超出可计算范围") from exc
    if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
        raise ToolError("结果不是有限数值")
    return value


def _eval_node(node: ast.AST) -> float | int:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, int | float):
            raise ToolError("只支持数字")
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        # 限制指数大小，避免 9**9**9 这类把进程算死
        if isinstance(node.op, ast.Pow) and (abs(right) > 100 or abs(left) > 10**6):
            raise ToolError("幂运算的参数过大")
        return _BIN_OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand))
    raise ToolError("表达式里包含不支持的写法")


def _format(value: float | int) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


class CalculatorTool:
    name = "calculator"
    description = (
        "计算算术表达式，支持 + - * / // % 与幂（** 或 ^）。需要精确数值时用它，不要心算。"
    )
    args_model = CalculatorArgs

    def spec(self) -> dict[str, Any]:
        from app.agent.tools.base import spec_of

        return spec_of(self)

    def run(
        self,
        args: BaseModel,
        user_id: int,  # noqa: ARG002 —— 这两个工具不读用户数据，签名统一保留
    ) -> str:
        assert isinstance(args, CalculatorArgs)
        return _format(evaluate(args.expression))
