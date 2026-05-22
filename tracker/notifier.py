import asyncio
import logging
from telegram import Bot
from telegram.error import TimedOut, NetworkError

from bot.config import BOT_TOKEN, TRACKER_DRY_RUN, TRACKER_TELEGRAM_CHAT_ID
from bot.formatters import format_tracker_daily_report, format_tracker_market_alert

logger = logging.getLogger("tracker.notifier")


class TrackerNotifier:
    def __init__(self):
        self.chat_id = TRACKER_TELEGRAM_CHAT_ID
        self.dry_run = TRACKER_DRY_RUN
        self.bot = Bot(BOT_TOKEN) if BOT_TOKEN and not self.dry_run else None
        self.max_retries = 3
        self.timeout = 60  # Increased from default ~20s to 60s

    async def _send_with_retry(self, send_func, *args, **kwargs) -> bool:
        """Send message with exponential backoff retry logic."""
        for attempt in range(self.max_retries):
            try:
                # Add timeout to kwargs
                kwargs['read_timeout'] = self.timeout
                kwargs['write_timeout'] = self.timeout
                kwargs['connect_timeout'] = self.timeout
                kwargs['pool_timeout'] = self.timeout

                await send_func(*args, **kwargs)
                return True
            except (TimedOut, NetworkError) as e:
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.warning(
                        "Telegram timeout on attempt %d/%d, retrying in %ds: %s",
                        attempt + 1,
                        self.max_retries,
                        wait_time,
                        str(e)
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        "Telegram send failed after %d attempts: %s",
                        self.max_retries,
                        str(e)
                    )
                    return False
            except Exception as e:
                logger.exception("Unexpected error sending Telegram message: %s", e)
                return False
        return False

    async def send_market_alert(self, alert_payload: dict) -> None:
        message = format_tracker_market_alert(alert_payload)
        if self.dry_run or not self.bot or not self.chat_id:
            print("[DRY_RUN] Market alert:\n", message)
            return

        success = await self._send_with_retry(
            self.bot.send_message,
            chat_id=self.chat_id,
            text=message,
            parse_mode="HTML"
        )
        if success:
            logger.info("Market alert sent successfully")
        else:
            logger.error("Failed to send market alert after retries")

    async def send_daily_report(self, report_payload: dict) -> None:
        message = format_tracker_daily_report(report_payload)
        if self.dry_run or not self.bot or not self.chat_id:
            print("[DRY_RUN] Daily report:\n", message)
            return

        success = await self._send_with_retry(
            self.bot.send_message,
            chat_id=self.chat_id,
            text=message,
            parse_mode="HTML"
        )
        if success:
            logger.info("Daily report sent successfully")
        else:
            logger.error("Failed to send daily report after retries")

