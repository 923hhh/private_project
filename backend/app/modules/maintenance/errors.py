"""检修域统一业务异常（映射为接口文档响应包）。"""


class MaintenanceAPIError(Exception):
    """携带 HTTP 状态与 business_code，由路由转换为 JSON 响应。"""

    def __init__(
        self,
        status_code: int,
        business_code: str,
        message: str,
        *,
        errors: list[dict] | None = None,
        data: dict | None = None,
    ) -> None:
        self.status_code = status_code
        self.business_code = business_code
        self.message = message
        self.errors = errors
        self.data = data
