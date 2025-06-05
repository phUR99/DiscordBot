import discord
from typing import Dict, List
from discord.ext import commands, tasks
from threading import Thread
from dotenv import load_dotenv
import os
import datetime
from holiday import is_holiday
import logging
import json
from tracking import (
    fetch_github_project_issues,
    is_target_issue,
    check_issue_created_by_users,
    get_daily_scrum_sub_issues,
    get_today_date_str,
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv(override=True)
channel_map = {}


bot_token = os.getenv("BOT_TOKEN")

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all(), help_command=None)

IS_HOLIDAY = None
USER_MAP = json.loads(os.getenv("USER_MAP", "{}"))


@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")


@bot.command(name="공지")
async def 공지(ctx):
    embed = discord.Embed(
        title="📢 최신 공지사항",
        description="공지 내용을 확인하세요!",
        color=0x00BFFF,
        url=os.getenv("NOTION"),
    )
    await ctx.send(embed=embed)


@bot.command(name="서비스")
async def 서비스(ctx):
    embed = discord.Embed(
        title="탐나라 서비스 접속",
        description="서비스에 접속하세요!",
        color=0x00BFFF,
        url=os.getenv("SERVICE"),
    )
    await ctx.send(embed=embed)


@bot.command(name="피드백")
async def 피드백(ctx):
    embed = discord.Embed(
        title="피드백 확인",
        description="피드백을 확인하세요!",
        color=0x00BFFF,
        url=os.getenv("FEEDBACK"),
    )
    await ctx.send(embed=embed)


channel_map = {}  # guild_id → {channel_type: channel_id}


@bot.event
async def on_ready():
    print(f"🤖 봇 로그인: {bot.user}")

    name_keywords = {
        "alarm": "alarm",
        "notice": "notice",
        "report": "report",
    }

    for guild in bot.guilds:
        guild_id = str(guild.id)
        if guild_id not in channel_map:
            channel_map[guild_id] = {}

        for channel in guild.text_channels:
            if not channel.permissions_for(guild.me).send_messages:
                continue

            for keyword, channel_type in name_keywords.items():
                if keyword in channel.name.lower():
                    if channel_type not in channel_map[guild_id]:
                        channel_map[guild_id][channel_type] = channel.id
                        print(
                            f"[{guild.name}] '{channel.name}' → '{channel_type}' 용도로 자동 등록"
                        )
    if not alarm.is_running():
        alarm.start()
    if not refresh_holiday.is_running():
        refresh_holiday.start()
    if not check_github_weekly_plan.is_running():
        check_github_weekly_plan.start()
    if not check_github_weekly_retrospect.is_running():
        check_github_weekly_retrospect.start()
    if not check_github_daily_scrum.is_running():
        check_github_daily_scrum.start()


@tasks.loop(hours=24)
async def refresh_holiday():
    global IS_HOLIDAY
    IS_HOLIDAY = is_holiday()


@tasks.loop(minutes=1)
async def alarm():
    now = datetime.datetime.now()
    current_time = now.strftime("%Y-%m-%d %H:%M:%S")
    if now.weekday() < 5 and now.hour == 9 and now.minute == 5 and not IS_HOLIDAY:
        logger.info(f"[{current_time}] 데일리 스크럼 알림 시작")
        description_text = "스크럼을 `09:10` 까지 작성해주세요!. \n\n Status : `Daily-Scrum` \n Title : `XX.XX.XX 이름` 형식으로 작성해주세요! \n `assignee` 할당해주세요!"
        link_text = f"스크럼 작성하러 가기:{os.getenv('DAILY_SCRUM')}"
        link_label, url = link_text.split(":", 1)

        embed = discord.Embed(
            title="** 📢 데일리 스크럼 ** ",
            description=(f"{description_text}\n\n" f"🔗 [{link_label}]({url})"),
            color=0x00BFFF,
        )
        for guild_id, channels in channel_map.items():
            alarm_id = channels.get("alarm")
            if alarm_id:
                channel = bot.get_channel(alarm_id)
                logger.info(
                    f"[{current_time}] 채널 {channel.name if channel else 'None'} 확인 중..."
                )
                if channel:
                    logger.info(f"[{current_time}] 데일리 스크럼 알림 전송 중...")
                    await channel.send(content="@everyone", embed=embed)
                    logger.info(f"[{current_time}] 데일리 스크럼 알림 전송 완료")

    if now.weekday() == 0 and now.hour == 10 and now.minute == 0 and not IS_HOLIDAY:
        logger.info(f"[{current_time}] 주간 계획 알림 시작")
        description_text = "계획 문서를 작성해주세요! \n\n Status : `Weekly-Planning` \n Title : `XX.XX.XX 이름` 형식으로 작성해주세요! \n `assignee` 할당해주세요!"
        link_text = f"계획 작성하러 가기:{os.getenv('WEEK_PLANNING')}"
        link_label, url = link_text.split(":", 1)

        embed = discord.Embed(
            title="** 📢 주간 계획 ** ",
            description=(f"{description_text}\n\n" f"🔗 [{link_label}]({url})"),
            color=0x00BFFF,
        )
        for guild_id, channels in channel_map.items():
            alarm_id = channels.get("alarm")
            if alarm_id:
                channel = bot.get_channel(alarm_id)
                logger.info(
                    f"[{current_time}] 채널 {channel.name if channel else 'None'} 확인 중..."
                )
                if channel:
                    logger.info(f"[{current_time}] 주간 계획 알림 전송 중...")
                    await channel.send(content="@everyone", embed=embed)
                    logger.info(f"[{current_time}] 주간 계획 알림 전송 완료")

    if now.weekday() == 3 and now.hour == 10 and now.minute == 0 and not IS_HOLIDAY:
        logger.info(f"[{current_time}] 주간 회고 알림 시작")
        description_text = "회고 문서를 작성해주세요! \n\n Status : `Weekly-Retrospect`, \n Title : `XX.XX.XX 이름` 형식으로 작성해주세요! \n `assignee` 할당해주세요!"
        link_text = f"회고 작성하러 가기:{os.getenv('WEEK_RETROSPECT')}"
        link_label, url = link_text.split(":", 1)

        embed = discord.Embed(
            title="** 📢 주간 회고 ** ",
            description=(f"{description_text}\n\n" f"🔗 [{link_label}]({url})"),
            color=0x00BFFF,
        )

        for guild_id, channels in channel_map.items():
            alarm_id = channels.get("alarm")
            if alarm_id:
                channel = bot.get_channel(alarm_id)
                logger.info(
                    f"[{current_time}] 채널 {channel.name if channel else 'None'} 확인 중..."
                )
                if channel:
                    logger.info(f"[{current_time}] 주간 회고 알림 전송 중...")
                    await channel.send(content="@everyone", embed=embed)
                    logger.info(f"[{current_time}] 주간 회고 알림 전송 완료")


@bot.command(name="도움말", aliases=["help"])
async def 도움말(ctx):
    embed = discord.Embed(
        title="🤖 사용 가능한 명령어 안내",
        description="아래는 이 봇에서 사용할 수 있는 명령어 목록입니다:",
        color=0x00BFFF,
    )

    embed.add_field(
        name="`!ping`",
        value="봇이 정상 작동 중인지 확인합니다.",
        inline=False,
    )

    embed.add_field(
        name="`!공지`", value="최신 노션 공지 링크를 제공합니다.", inline=False
    )
    embed.add_field(
        name="`!서비스`", value="탐나라 서비스 링크를 제공합니다.", inline=False
    )
    embed.add_field(
        name="`!피드백`",
        value="피드백 구글스프레드 시트 링크를 제공합니다.",
        inline=False,
    )

    embed.add_field(
        name="`!도움말` 또는 `!help`",
        value="이 도움말 메시지를 보여줍니다.",
        inline=False,
    )

    await ctx.send(embed=embed)


def get_unsubmitted_user_ids(
    result: Dict[str, bool], user_map: Dict[str, str]
) -> List[str]:
    ids = []
    for user, created in result.items():
        if not created:
            mention = user_map.get(user, "")
            ids.append(mention)
    return ids


@tasks.loop(hours=1)
async def check_github_weekly_plan():
    try:
        now = datetime.datetime.now()
        current_time = now.strftime("%Y-%m-%d %H:%M:%S")
        if not (
            now.weekday() == 0
            and now.hour >= 10
            and now.hour <= 13
            and now.minute == 0
            and not IS_HOLIDAY
        ):
            return
        logger.info(f"[{current_time}] 주간 계획 체크 시작")
        issues = await fetch_github_project_issues()
        target_issues = [
            item for item in issues if is_target_issue(item, "Weekly-Planning")
        ]
        logger.info(f"[{current_time}] [주간 계획] 대상 이슈 수: {len(target_issues)}")
        result = check_issue_created_by_users(target_issues, USER_MAP)
        mentions = get_unsubmitted_user_ids(result, USER_MAP)
        logger.info(f"[{current_time}] [주간 계획] 미작성자 수: {len(mentions)}")
        description_text = "계획 문서를 작성해주세요! \n\n Status : `Weekly-Planning`, \n Title : `XX.XX.XX 이름` 형식으로 작성해주세요! \n `assignee` 할당해주세요!"
        link_text = f"계획 작성하러 가기:{os.getenv('WEEK_PLANNING')}"
        link_label, url = link_text.split(":", 1)
        for mention in mentions:
            embed = discord.Embed(
                title="📢 주간 계획 미작성 알림",
                description=(f"{description_text}\n\n" f"🔗 [{link_label}]({url})"),
                color=discord.Color.red(),
            )
            for guild_id, channels in channel_map.items():
                channel_id = channels.get("alarm")
                if channel_id:
                    channel = bot.get_channel(channel_id)
                    if channel:
                        await channel.send(content=f"<@{mention}>", embed=embed)
    except Exception:
        logger.exception("check_github_weekly_plan 실행 중 오류 발생")


@tasks.loop(hours=1)
async def check_github_weekly_retrospect():
    try:
        now = datetime.datetime.now()
        current_time = now.strftime("%Y-%m-%d %H:%M:%S")
        if not (
            now.weekday() == 3
            and now.hour >= 10
            and now.hour <= 16
            and now.minute == 0
            and not IS_HOLIDAY
        ):
            return
        logger.info(f"[{current_time}] 주간 회고 체크 시작")
        issues = await fetch_github_project_issues()
        target_issues = [
            item for item in issues if is_target_issue(item, "Weekly-Retrospect")
        ]
        logger.info(f"[{current_time}] [주간 회고] 대상 이슈 수: {len(target_issues)}")
        result = check_issue_created_by_users(target_issues, USER_MAP)
        mentions = get_unsubmitted_user_ids(result, USER_MAP)
        logger.info(f"[{current_time}] [주간 회고] 미작성자 수: {len(mentions)}")
        description_text = "회고 문서를 작성해주세요! \n\n Status : `Weekly-Restrospect`, \n Title : `XX.XX.XX 이름` 형식으로 작성해주세요! \n `assignee` 할당해주세요!"
        link_text = f"회고 작성하러 가기:{os.getenv('WEEK_RETROSPECT')}"
        link_label, url = link_text.split(":", 1)
        for mention in mentions:
            embed = discord.Embed(
                title="📢 주간 회고 미작성 알림",
                description=(f"{description_text}\n\n" f"🔗 [{link_label}]({url})"),
                color=discord.Color.red(),
            )
            for guild_id, channels in channel_map.items():
                channel_id = channels.get("alarm")
                if channel_id:
                    channel = bot.get_channel(channel_id)
                    if channel:
                        await channel.send(content=f"<@{mention}>", embed=embed)
    except Exception:
        logger.exception("check_github_weekly_retrospect 실행 중 오류 발생")


@tasks.loop(minutes=10)
async def check_github_daily_scrum():
    try:
        now = datetime.datetime.now()
        current_time = now.strftime("%Y-%m-%d %H:%M:%S")
        if not (
            now.weekday() < 5
            and now.hour == 9
            and now.minute >= 10
            and now.minute < 30
            and not IS_HOLIDAY
        ):
            return
        logger.info(f"[{current_time}] 데일리 스크럼 체크 시작")
        issues = await fetch_github_project_issues()
        sub_issues = await get_daily_scrum_sub_issues(
            issues,
            get_today_date_str(),
        )
        logger.info(f"[{current_time}] [데일리 스크럼] 서브이슈 수: {len(sub_issues)}")

        # 서브이슈 작성자 추출
        submitted_users = set()
        for sub_issue in sub_issues:
            for assignee in sub_issue.get("assignees", []):
                if "login" in assignee:
                    submitted_users.add(assignee["login"].lower())

        # 미작성자 확인
        result = {user: user.lower() in submitted_users for user in USER_MAP}
        logging.info(f"{result}")

        mentions = get_unsubmitted_user_ids(result, USER_MAP)
        description_text = "스크럼 문서를 작성해주세요! \n\n 오늘 날짜 밑의 `sub-issue`를 작성해주세요! \n Title : `XX.XX.XX 이름` 형식으로 작성해주세요! \n `assignee` 할당해주세요!"
        link_text = f"스크럼 작성하러 가기:{os.getenv('DAILY_SCRUM')}"
        link_label, url = link_text.split(":", 1)
        for mention in mentions:
            embed = discord.Embed(
                title="📢 데일리 스크럼 미작성 알림",
                description=(f"{description_text}\n\n" f"🔗 [{link_label}]({url})"),
                color=discord.Color.red(),
            )
            for guild_id, channels in channel_map.items():
                channel_id = channels.get("alarm")
                if channel_id:
                    channel = bot.get_channel(channel_id)
                    if channel:
                        await channel.send(content=f"<@{mention}>", embed=embed)
    except Exception:
        logger.exception("check_github_weekly_retrospect 실행 중 오류 발생")


bot.run(bot_token)
# 간단한 웹서버 생성 (슬립 방지용)
