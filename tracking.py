import json
import re
from dotenv import load_dotenv
import os
import aiohttp
import logging
from typing import List, Dict, Any, Set, Optional
import datetime

logger = logging.getLogger(__name__)
load_dotenv(override=True)

# 환경 변수 로드 및 검증
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
PROJECT_ID = os.getenv("GITHUB_PROJECT_ID")
ORG_LOGIN = os.getenv("GITHUB_ORG")

if not all([GITHUB_TOKEN, PROJECT_ID, ORG_LOGIN]):
    raise ValueError(
        "필수 환경 변수가 설정되지 않았습니다: GITHUB_TOKEN, GITHUB_PROJECT_ID, GITHUB_ORG"
    )

# 디스코드-깃허브 사용자 매핑 (환경 변수에서 로드)
USER_MAP = os.getenv("USER_MAP", "{}")
try:
    user_map = json.loads(USER_MAP)
except json.JSONDecodeError:
    logger.error("USER_MAP 환경 변수가 올바른 JSON 형식이 아닙니다.")
    user_map = {}

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Content-Type": "application/json",
    "X-GitHub-Api-Version": "2022-11-28",
}


async def fetch_github_project_issues() -> List[Dict[str, Any]]:
    """GitHub Project v2에서 이슈 목록을 가져옵니다."""
    url = "https://api.github.com/graphql"
    query = {
        "query": f"""
        query {{
            organization(login: "{ORG_LOGIN}") {{
                projectV2(number: {PROJECT_ID}) {{
                    items(last: 100) {{
                        nodes {{
                            fieldValues(first: 100) {{
                                nodes {{
                                    __typename
                                    ... on ProjectV2ItemFieldSingleSelectValue {{
                                        name
                                        field {{
                                            ... on ProjectV2SingleSelectField {{
                                                name
                                            }}
                                        }}
                                    }}
                                    ... on ProjectV2ItemFieldTextValue {{
                                        text
                                        field {{
                                            ... on ProjectV2Field {{
                                                name
                                            }}
                                        }}
                                    }}
                                    ... on ProjectV2ItemFieldNumberValue {{
                                        number
                                        field {{
                                            ... on ProjectV2Field {{
                                                name
                                            }}
                                        }}
                                    }}
                                    ... on ProjectV2ItemFieldDateValue {{
                                        date
                                        field {{
                                            ... on ProjectV2Field {{
                                                name
                                            }}
                                        }}
                                    }}
                                }}
                            }}
                            content {{
                                ... on Issue {{
                                    title
                                    url
                                    body
                                    assignees(first: 10) {{
                                        nodes {{
                                            login
                                        }}
                                    }}
                                }}
                            }}
                            createdAt
                        }}
                    }}
                }}
            }}
        }}
        """
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=HEADERS, json=query) as response:
                if response.status != 200:
                    logger.error(f"GitHub API 요청 실패: HTTP {response.status}")
                    return []

                data = await response.json()

                # 응답 로깅 (민감한 정보 제외)
                logger.debug(f"GitHub GraphQL 응답 상태: {response.status}")

                if "errors" in data:
                    logger.error(f"GitHub API Error: {data['errors']}")
                    return []

                # 데이터 구조 검증
                try:
                    items = data["data"]["organization"]["projectV2"]["items"]["nodes"]
                    logger.info(f"가져온 프로젝트 아이템 수: {len(items)}")
                    return items
                except KeyError as e:
                    logger.error(f"예상하지 못한 응답 구조: {e}")
                    return []

    except aiohttp.ClientError as e:
        logger.error(f"HTTP 클라이언트 오류: {e}")
        return []
    except Exception as e:
        logger.exception(f"GraphQL 요청 중 예상치 못한 오류 발생: {e}")
        return []


def extract_assignees_by_prefix(items: List[Dict[str, Any]], prefix: str) -> Set[str]:
    """특정 접두사로 시작하는 이슈들의 담당자를 추출합니다."""
    users = set()

    for item in items:
        content = item.get("content")
        if not content:
            continue

        title = content.get("title", "")
        if not title.startswith(prefix):
            continue

        assignees = content.get("assignees", {}).get("nodes", [])
        for assignee in assignees:
            if assignee and "login" in assignee:
                users.add(assignee["login"])

    return users


def get_field_value(item: Dict[str, Any], field_name: str) -> Optional[Any]:
    """프로젝트 아이템에서 특정 필드의 값을 가져옵니다."""
    field_values = item.get("fieldValues", {}).get("nodes", [])

    for field in field_values:
        # 필드 객체에서 필드 이름 가져오기
        field_obj = field.get("field")
        if not field_obj:
            continue

        actual_field_name = field_obj.get("name")
        if actual_field_name != field_name:
            continue

        # 필드 타입에 따라 값 반환
        field_type = field.get("__typename")

        if field_type == "ProjectV2ItemFieldSingleSelectValue":
            return field.get("name")
        elif field_type == "ProjectV2ItemFieldTextValue":
            return field.get("text")
        elif field_type == "ProjectV2ItemFieldNumberValue":
            return field.get("number")
        elif field_type == "ProjectV2ItemFieldDateValue":
            return field.get("date")
        elif field_type == "ProjectV2ItemFieldUserValue":
            users = field.get("users", {}).get("nodes", [])
            return [user.get("login") for user in users] if users else None
        elif field_type == "ProjectV2ItemFieldRepositoryValue":
            return field.get("repository", {}).get("name")
        elif field_type == "ProjectV2ItemFieldMilestoneValue":
            return field.get("milestone", {}).get("title")
        elif field_type == "ProjectV2ItemFieldLabelValue":
            labels = field.get("labels", {}).get("nodes", [])
            return [label.get("name") for label in labels] if labels else None
        elif field_type == "ProjectV2ItemFieldPullRequestValue":
            prs = field.get("pullRequests", {}).get("nodes", [])
            return [pr.get("title") for pr in prs] if prs else None
        else:
            logger.warning(f"알 수 없는 필드 타입: {field_type}")

    return None


def is_target_issue(item: Dict[str, Any], target: str) -> bool:
    """이슈가 대상 이슈인지 확인합니다 (Status가 '주간 계획'이고 제목이 날짜 형식)."""
    # Status 필드 값 가져오기
    status = get_field_value(item, "Status")

    # 제목 가져오기
    content = item.get("content")
    if not content:
        logger.debug("Issue에 content가 없습니다.")
        return False

    title = content.get("title", "")

    # 모든 필드값 디버깅 출력
    field_values = item.get("fieldValues", {}).get("nodes", [])
    logger.info(f"=== Issue 디버깅 ===")
    logger.info(f"제목: '{title}'")
    logger.info(f"Status 필드값: '{status}'")
    logger.info(f"모든 필드값:")
    for field in field_values:
        field_obj = field.get("field", {})
        field_name = field_obj.get("name", "Unknown")
        field_type = field.get("__typename", "Unknown")

        if field_type == "ProjectV2ItemFieldSingleSelectValue":
            value = field.get("name")
        elif field_type == "ProjectV2ItemFieldTextValue":
            value = field.get("text")
        elif field_type == "ProjectV2ItemFieldNumberValue":
            value = field.get("number")
        elif field_type == "ProjectV2ItemFieldDateValue":
            value = field.get("date")
        elif field_type == "ProjectV2ItemFieldUserValue":
            users = field.get("users", {}).get("nodes", [])
            value = [user.get("login") for user in users] if users else "No users"
        elif field_type == "ProjectV2ItemFieldRepositoryValue":
            value = field.get("repository", {}).get("name", "No repo")
        elif field_type == "ProjectV2ItemFieldMilestoneValue":
            value = field.get("milestone", {}).get("title", "No milestone")
        elif field_type == "ProjectV2ItemFieldLabelValue":
            labels = field.get("labels", {}).get("nodes", [])
            value = [label.get("name") for label in labels] if labels else "No labels"
        elif field_type == "ProjectV2ItemFieldPullRequestValue":
            prs = field.get("pullRequests", {}).get("nodes", [])
            value = [pr.get("title") for pr in prs] if prs else "No PRs"
        else:
            value = f"Unsupported type: {field_type}"

        logger.info(f"  - {field_name} ({field_type}): {value}")

    # Status가 '주간 계획'인지 확인 (여러 가능한 값들 체크)
    possible_status_values = target
    status_match = status == possible_status_values

    return status_match


def sort_items_by_created_at_desc(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """createdAt 기준 내림차순 정렬 (최신순)."""

    def parse_date(item):
        return datetime.datetime.fromisoformat(
            item.get("createdAt", "1970-01-01T00:00:00Z").replace("Z", "+00:00")
        )

    return sorted(items, key=parse_date, reverse=True)


def get_discord_username(github_username: str) -> str:
    """GitHub 사용자명을 Discord 사용자명으로 변환합니다."""
    return user_map.get(github_username, github_username)


async def fetch_all_github_project_issues() -> List[Dict[str, Any]]:
    """GitHub Project v2에서 모든 이슈를 페이지네이션으로 가져옵니다."""
    all_items = []
    cursor = None
    page = 1

    while True:
        logger.info(f"페이지 {page} 가져오는 중...")

        # 커서가 있으면 after 파라미터 추가
        after_param = f', after: "{cursor}"' if cursor else ""

        url = "https://api.github.com/graphql"
        query = {
            "query": f"""
            query {{
                organization(login: "{ORG_LOGIN}") {{
                    projectV2(number: {PROJECT_ID}) {{
                        items(first: 100, orderBy: {{field: CREATED_AT, direction: DESC}}{after_param}) {{
                            pageInfo {{
                                hasNextPage
                                endCursor
                            }}
                            nodes {{
                                id
                                fieldValues(first: 20) {{
                                    nodes {{
                                        __typename
                                        ... on ProjectV2ItemFieldSingleSelectValue {{
                                            name
                                            field {{
                                                ... on ProjectV2SingleSelectField {{
                                                    name
                                                }}
                                            }}
                                        }}
                                        ... on ProjectV2ItemFieldTextValue {{
                                            text
                                            field {{
                                                ... on ProjectV2Field {{
                                                    name
                                                }}
                                            }}
                                        }}
                                        ... on ProjectV2ItemFieldNumberValue {{
                                            number
                                            field {{
                                                ... on ProjectV2Field {{
                                                    name
                                                }}
                                            }}
                                        }}
                                        ... on ProjectV2ItemFieldDateValue {{
                                            date
                                            field {{
                                                ... on ProjectV2Field {{
                                                    name
                                                }}
                                            }}
                                        }}
                                        ... on ProjectV2ItemFieldUserValue {{
                                            users(first: 10) {{
                                                nodes {{
                                                    login
                                                }}
                                            }}
                                            field {{
                                                ... on ProjectV2Field {{
                                                    name
                                                }}
                                            }}
                                        }}
                                    }}
                                }}
                                content {{
                                    ... on Issue {{
                                        title
                                        url
                                        createdAt
                                        updatedAt
                                        assignees(first: 10) {{
                                            nodes {{
                                                login
                                            }}
                                        }}
                                    }}
                                }}
                                createdAt
                                updatedAt
                            }}
                        }}
                    }}
                }}
            }}
            """
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=HEADERS, json=query) as response:
                    if response.status != 200:
                        logger.error(f"GitHub API 요청 실패: HTTP {response.status}")
                        break

                    data = await response.json()

                    if "errors" in data:
                        logger.error(f"GitHub API Error: {data['errors']}")
                        break

                    items_data = data["data"]["organization"]["projectV2"]["items"]
                    items = items_data["nodes"]
                    page_info = items_data["pageInfo"]

                    all_items.extend(items)
                    logger.info(
                        f"페이지 {page}: {len(items)}개 아이템 추가 (전체: {len(all_items)}개)"
                    )

                    # 다음 페이지가 있는지 확인
                    if not page_info["hasNextPage"]:
                        break

                    cursor = page_info["endCursor"]
                    page += 1

                    # 안전장치: 최대 10페이지까지만
                    if page > 10:
                        logger.warning("최대 페이지 수 (10)에 도달했습니다.")
                        break

        except Exception as e:
            logger.exception(f"페이지 {page} 가져오기 중 오류: {e}")
            break

    logger.info(f"총 {len(all_items)}개 아이템을 가져왔습니다.")
    return all_items


# 사용 예시 함수들
async def debug_all_issues() -> None:
    """모든 이슈의 정보를 디버깅 목적으로 출력합니다."""
    items = await fetch_all_github_project_issues()  # 모든 페이지 가져오기
    logger.info(f"전체 아이템 수: {len(items)}")

    for i, item in enumerate(items[:10]):  # 처음 10개만 출력
        content = item.get("content")
        if content:
            title = content.get("title", "")
            created_at = content.get("createdAt", "Unknown")
            logger.info(f"[{i+1}] 제목: {title} (생성: {created_at})")
        else:
            logger.info(f"[{i+1}] Content 없음")


async def get_weekly_plan_issues() -> List[Dict[str, Any]]:
    """주간 계획 이슈들을 가져옵니다."""
    items = await fetch_all_github_project_issues()  # 모든 페이지에서 검색
    return [item for item in items if is_target_issue(item)]


async def get_assignees_for_prefix(prefix: str) -> Set[str]:
    """특정 접두사로 시작하는 이슈들의 담당자를 가져옵니다."""
    items = await fetch_all_github_project_issues()  # 모든 페이지에서 검색
    github_users = extract_assignees_by_prefix(items, prefix)
    return {get_discord_username(user) for user in github_users}


# --- 날짜 추출 ---
def extract_date_from_title(title: str) -> str:
    match = re.match(r"(\d{2}\.\d{2}\.\d{2})", title)
    return match.group(1) if match else ""


# --- 오늘 날짜 반환 (YY.MM.DD 포맷) ---
def get_today_date_str() -> str:
    return datetime.datetime.today().strftime("%y.%m.%d")


# --- 담당자 이슈 작성 여부 확인 ---
def check_issue_created_by_users(
    issues: List[Dict[str, Any]], expected_users: List[str]
) -> Dict[str, bool]:
    created_by = set()
    today = get_today_date_str()
    for item in issues:
        content = item.get("content", {})
        title = content.get("title", "")
        assignees = content.get("assignees", {}).get("nodes", [])
        issue_date = extract_date_from_title(title)

        if issue_date != today:
            continue

        for a in assignees:
            if "login" in a:
                created_by.add(a["login"].lower())

    return {user: user.lower() in created_by for user in expected_users}


async def get_daily_scrum_sub_issues(issues: list[dict], today: str) -> list[dict]:
    """
    오늘 날짜에 해당하는 Daily-Scrum 상위 이슈 아래의 서브 이슈들을 추출합니다.

    Parameters:
    - issues: GitHub Project v2 이슈 데이터 리스트
    - today: 'YY.MM.DD' 형식의 오늘 날짜 문자열

    Returns:
    - 해당 날짜에 대응하는 Daily-Scrum 하위 이슈 리스트
    """
    logger.info(f"=== 서브이슈 검색 시작 (날짜: {today}) ===")

    # 상위 Daily-Scrum 이슈 찾기 (title이 정확히 오늘 날짜이고 Status가 Daily-Scrum인 이슈)
    parent_issue = next(
        (
            item
            for item in issues
            if item.get("content", {}).get("title") == today
            and get_field_value(item, "Status") == "Daily-Scrum"
        ),
        None,
    )

    if parent_issue:
        logger.info("=== 상위 이슈 정보 ===")
        logger.info(f"제목: {parent_issue.get('content', {}).get('title')}")
        logger.info(f"URL: {parent_issue.get('content', {}).get('url')}")
        logger.info(f"상태: {get_field_value(parent_issue, 'Status')}")
        logger.info(f"생성일: {parent_issue.get('createdAt')}")
    else:
        logger.info("상위 이슈를 찾을 수 없습니다.")
        return []

    # 서브이슈 찾기 (title이 '오늘 날짜 + 공백 + 이름' 형식인 이슈들)
    sub_issues = []
    for item in issues:
        content = item.get("content", {})
        title = content.get("title", "")

        # 정확히 'YY.MM.DD 이름' 형식인지 확인
        if title.startswith(today + " "):
            logger.info(f"서브이슈 발견: {title}")
            sub_issues.append(
                {
                    "body": title,
                    "url": content.get("url", ""),
                    "assignees": content.get("assignees", {}).get("nodes", []),
                }
            )

    logger.info(f"=== 서브이슈 검색 결과 ({len(sub_issues)}개) ===")
    return sub_issues


def get_field_value(item: dict, field_name: str) -> str:
    for field in item.get("fieldValues", {}).get("nodes", []):
        if field.get("field", {}).get("name") == field_name:
            return field.get("name") or field.get("text", "")
    return ""
