import logging
from datetime import datetime, timedelta, timezone
from functools import wraps

from py3cw.request import Py3CW

logger = logging.getLogger(__name__)

class Freqtrade3cw:

    @staticmethod
    def buy_signal(func):
        @wraps(func)
        def wrapper_decorator(*args, **kwargs):
            assert func.__name__ == 'populate_buy_trend', "@buy_signal should only decorate the 'populate_buy_trend' method."

            dataframe = func(*args, **kwargs)

            strategy, _, metadata = args

            if strategy.dp.runmode.value not in ('live', 'dry_run'):
                return dataframe

            assert '3commas' in strategy.config, "Missing 3commas configuration!"

            if not hasattr(strategy, 'custom_3commas'):
                strategy.custom_3commas = dict()

            if metadata['pair'] not in strategy.custom_3commas:
                strategy.custom_3commas[metadata['pair']] = dict()

            last_candle = dataframe.iloc[-1]

            if last_candle.buy == 1:
                last_buy_date = strategy.custom_3commas[metadata['pair']].get('last_buy_date', datetime.now(timezone.utc) - timedelta(minutes=1))

                # We don't want to spam 3commas with API calls
                if datetime.now(timezone.utc) - last_buy_date > timedelta(seconds=30):
                    strategy.custom_3commas[metadata['pair']]['last_buy_date'] = datetime.now(timezone.utc)

                    coin, currency = metadata['pair'].split('/')

                    p3cw = Py3CW(
                        key=strategy.config['3commas']['key'],
                        secret=strategy.config['3commas']['secret'],
                    )

                    bot_ids = []

                    if 'bot_id' in strategy.config['3commas'] and 'bot_ids' not in strategy.config['3commas']:
                        bot_ids.append(strategy.config['3commas']['bot_id'])
                        logger.warning(f"3Commas: Deprecated bot_id settings are present, please update your config!")

                    if 'bot_ids' in strategy.config['3commas']:
                        bot_ids += strategy.config['3commas']['bot_ids']

                    for bot_id in bot_ids:
                        logger.info(f"3Commas: Sending buy signal for {metadata['pair']} to 3commas bot_id={bot_id}")

                        error, data = p3cw.request(
                            entity="bots",
                            action="start_new_deal",
                            action_id=f"{bot_id}",
                            payload={  # type: ignore
                                "bot_id": f"{bot_id}",
                                "pair": f"{currency}_{coin}",
                            },
                        )

                        if error:
                            logger.error(f"3Commas: {error['msg']}")
                        else:
                            try:  # try/except because the response isn't always clear
                                logger.info(f"3Commas: {data['bot_events'][0]['message']}")  # type: ignore
                            except (IndexError, KeyError):
                                pass


            return dataframe
        return wrapper_decorator
