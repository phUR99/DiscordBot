import discord
import asyncio
from discord.ext import commands, tasks
from dotenv import load_dotenv
import os
import datetime
from holiday import is_holiday
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv(override=True)
channel_map = {}


bot_token = os.getenv("BOT_TOKEN")

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all(), help_command=None)

IS_HOLIDAY = None


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


@tasks.loop(hours=24)
async def refresh_holiday():
    global IS_HOLIDAY
    IS_HOLIDAY = is_holiday()


@tasks.loop(seconds=10)
async def alarm():
    now = datetime.datetime.now()
    logging.info(
        f"{now.weekday() < 5 and now.hour >= 18 and now.minute >= 1 and IS_HOLIDAY}"
    )
    if (
        now.weekday() < 5
        and now.hour == 9
        and now.minute >= 0
        and now.minute <= 10
        and not IS_HOLIDAY
        or True
    ):
        description_text = "스크럼을 `09:10` 까지 작성해주세요!"
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
                logging.info(f"채널 확인...")
                if channel:
                    logging.info(f"전송 중...")
                    await channel.send(content="@everyone", embed=embed)
    if (
        now.weekday() == 3
        and now.hour >= 10
        and now.hour <= 17
        and now.minute == 0
        and not IS_HOLIDAY
        or True
    ):
        description_text = "계획 문서를 `13:30` 까지 작성해주세요!"
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
                logging.info(f"채널 확인...")
                if channel:
                    logging.info(f"전송 중...")
                    await channel.send(content="@everyone", embed=embed)
    if (
        now.weekday() == 0
        and now.hour >= 10
        and now.hour <= 2
        and now.minute == 0
        and not IS_HOLIDAY
        or True
    ):
        description_text = "회고 문서를 `16:30` 까지 작성해주세요!"
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
                logging.info(f"채널 확인...")
                if channel:
                    logging.info(f"전송 중...")
                    await channel.send(content="@everyone", embed=embed)


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


bot.run(bot_token)
