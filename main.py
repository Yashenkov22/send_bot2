import asyncio

import redis

import uvicorn

import redis.asyncio
import redis.asyncio.client
from uvicorn import Config, Server

from pyrogram import Client

from starlette.middleware.cors import CORSMiddleware

from fastapi import FastAPI, APIRouter

from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage

from sqlalchemy.engine import create_engine
from sqlalchemy.orm import sessionmaker, Session

from db.base import engine, session, Base

from middlewares.db import DbSessionMiddleware

from config import (TOKEN,
                    db_url,
                    PUBLIC_URL,
                    API_ID,
                    API_HASH,
                    REDIS_HOST,
                    REDIS_PASSWORD)
from handlers import (main_router, send_comment,
                      send_mass_message, send_review, test_result_chat_link,
                      test_send,
                      test_send_info,
                      result_chat_link)


###DEV###

#DATABASE
# engine = create_engine(db_url,
#                        echo=True)

# Base.prepare(engine, reflect=True)

# session = sessionmaker(engine, expire_on_commit=False)

#Initialize Redis storage
# redis_client = redis.asyncio.client.Redis(host=REDIS_HOST,
#                                           password=REDIS_PASSWORD)
# storage = RedisStorage(redis=redis_client)


#TG BOT
bot = Bot(TOKEN, parse_mode="HTML")

#####
# api_client = Client('my_account',
#                     api_id=API_ID,
#                     api_hash=API_HASH)
#####

dp = Dispatcher()
dp.include_router(main_router)

#Add session and database connection in handlers 
dp.update.middleware(DbSessionMiddleware(session_pool=session))

#Initialize web server
app = FastAPI(docs_url='/docs_send')
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
event_loop = asyncio.get_event_loop()
config = Config(app=app,
                loop=event_loop,
                host='0.0.0.0',
                port=8002)
server = Server(config)


fast_api_router = APIRouter(prefix='/bot_api')
# app.include_router(fast_api_router)

#For set webhook
WEBHOOK_PATH = f'/webhook_send'

#Set webhook and create database on start
@app.on_event('startup')
async def on_startup():
    await bot.set_webhook(f"{PUBLIC_URL}{WEBHOOK_PATH}",
                          drop_pending_updates=True,
                          allowed_updates=['message', 'callback_query'])
    
    # Base.prepare(engine, reflect=True)


#Endpoint for checking
@app.get(WEBHOOK_PATH)
async def any():
    return {'status': 'ok'}


#Endpoint for incoming updates
@app.post(WEBHOOK_PATH)
async def bot_webhook(update: dict):
    tg_update = types.Update(**update)
    await dp.feed_update(bot=bot, update=tg_update)


@app.get('/send_to_tg_group')
async def send_to_tg_group(user_id: int,
                           order_id: int,
                           marker: str):
    await test_send(user_id=user_id,
                    order_id=order_id,
                    marker=marker,
                    session=session(),
                    bot=bot)


@app.get('/send_to_tg_group_review')
async def send_to_tg_group_review(review_id: int):
    await send_review(review_id=review_id,
                      session=session(),
                      bot=bot)


@app.get('/send_to_tg_group_comment')
async def send_to_tg_group_comment(comment_id: int):
    await send_comment(comment_id=comment_id,
                      session=session(),
                      bot=bot)


@app.get('/send_result_chat_link')
async def send_result_chat_link(result_text: str):
    await result_chat_link(result_text,
                           bot=bot)
    

@app.get('/test_send_result_chat_link')
async def send_result_chat_link(result_text: str):
    await test_result_chat_link(result_text,
                                bot=bot)


@app.get('/send_mass_message_info')
async def send_mass_message_info(execute_time,
                           start_users_count,
                           end_users_count):
    await test_send_info(execute_time=execute_time,
                    start_users_count=start_users_count,
                    end_users_count=end_users_count,
                    session=session(),
                    bot=bot)
#Endpoint for mass send message
# @app.get('/send_mass_message')
# async def send_mass_message_for_all_users(name_send: str):
#     await send_mass_message(bot=bot,
#                             session=session(),
#                             name_send=name_send)
    

# app.include_router(fast_api_router)
# fast_api_router = APIRouter()

# @fast_api_router.get('/test')
# async def test_api():
#     Guest = Base.classes.general_models_guest

#     # with session() as conn:
#     #     conn: Session
#     #     conn.query(Guest)
#     await bot.send_message('686339126', 'what`s up')
    
# app = FastAPI()

# bot = Bot(TOKEN, parse_mode="HTML")

###

# fast_api_router = APIRouter()

# @fast_api_router.get('/test')
# async def test_api():
#     Guest = Base.classes.general_models_guest

#     # with session() as conn:
#     #     conn: Session
#     #     conn.query(Guest)
#     await send_mass_message(bot=bot,
#                             session=session())
    # await bot.send_message('686339126', 'what`s up')

# app.include_router(fast_api_router)
    ###


# async def main():
    # bot = Bot(TOKEN, parse_mode="HTML")
    # w = await bot.get_my_commands()
    # print(w)
    # await bot.set_my_commands([
    #     types.BotCommand(command='send',description='send mass message'),
    # ])
    # w = await bot.get_my_commands()
    # print(w)


    # api_client = Client('my_account',
    #                     api_id=API_ID,
    #                     api_hash=API_HASH)



    # dp = Dispatcher()
    # dp.include_router(main_router)
    # dp.update.middleware(DbSessionMiddleware(session_pool=session))

    # engine = create_engine(db_url,
    #                        echo=True)

    # Base.prepare(engine, reflect=True)
    

    # await bot.delete_webhook(drop_pending_updates=True)
    # await dp.start_polling(bot)
    # await event_loop.run_until_complete(server.serve())
    # uvicorn.run('main:app', host='0.0.0.0', port=8001)


# if __name__ == '__main__':
#     asyncio.run(main())
if __name__ == '__main__':
    event_loop.run_until_complete(server.serve())