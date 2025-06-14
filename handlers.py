import os
import json

import pytz

from datetime import datetime

import aiohttp

from aiogram import Router, types, Bot, F
from aiogram.types import BufferedInputFile, URLInputFile
from aiogram.utils.media_group import MediaGroupBuilder
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from pyrogram import Client

from sqlalchemy.orm import Session, joinedload, sessionmaker
from sqlalchemy import and_, insert, select, update, or_

from config import BEARER_TOKEN, FEEDBACK_REASON_PREFIX

from keyboards import (create_start_keyboard,
                       create_start_inline_keyboard,
                       create_swift_start_kb,
                       add_cancel_btn_to_kb,
                       create_kb_to_main,
                       create_swift_sepa_kb,
                       create_support_kb,
                       create_feedback_form_reasons_kb,
                       reason_dict,
                       create_feedback_confirm_kb,
                       create_confirm_swift_sepa_kb)

from states import SwiftSepaStates, FeedbackFormStates

from utils.handlers import try_add_file_ids_to_db, try_add_file_ids, swift_sepa_data

from db.base import Base


main_router = Router()

start_text = '💱<b>Добро пожаловать в MoneySwap!</b>\n\nНаш бот поможет найти лучшую сделку под вашу задачу 💸\n\n👉🏻 <b>Чтобы начать поиск</b>, выберите категорию “безналичные”, “наличные” или “Swift/Sepa” и нажмите на нужную кнопку ниже.\n\nЕсли есть какие-то вопросы, обращайтесь <a href="https://t.me/MoneySwap_support">Support</a> или <a href="https://t.me/moneyswap_admin">Admin</a>. Мы всегда готовы вам помочь!'

moscow_tz = pytz.timezone('Europe/Moscow')

@main_router.message(Command('start'))
async def start(message: types.Message | types.CallbackQuery,
                session: Session,
                state: FSMContext,
                bot: Bot,
                text_msg: str = None):
    is_callback = isinstance(message, types.CallbackQuery)

    # data = await state.get_data()
    # main_menu_msg: tuple[str,str] = data.get('main_menu_msg')

    # if main_menu_msg:
    #     try:
    #         await bot.delete_message(*main_menu_msg)
    #         # await main_menu_msg.delete()
    #     except Exception:
    #         pass
    # print(bool(prev_start_msg))

    # if not prev_start_msg:
        # await bot.delete_message(message.chat.id,
        #                          start_msg)
    utm_source = None

    if isinstance(message, types.Message):
        query_param = message.text.split()

        if len(query_param) > 1:
            utm_source = query_param[-1]
            # print('UTM SOURCE')
            # print(utm_source)
            # print(len(utm_source))
            # print('*' * 10)
        
    Guest = Base.classes.general_models_guest

    tg_id = message.from_user.id
    guest = session.query(Guest)\
                    .where(Guest.tg_id == tg_id)\
                    .first()
    
    if isinstance(message, types.CallbackQuery):
        message = message.message

    # print(guest)
    if not guest:
        value_dict = {
            'username': message.from_user.username,
            'tg_id': tg_id,
            'first_name': message.from_user.first_name,
            'last_name': message.from_user.last_name,
            'language_code': message.from_user.language_code,
            'is_premium': bool(message.from_user.is_premium),
            'is_active': True,
        }

        if utm_source:
            value_dict.update(
                {
                    'utm_source': utm_source,
                }
            )
        session.execute(insert(Guest).values(**value_dict))
        session.commit()

    # print(message.from_user.username)
    # print(message.from_user.id)
    # start_kb = create_start_keyboard(tg_id)

    start_kb = create_start_inline_keyboard(tg_id)
    # text = start_text if text_msg is None else text_msg
    
    # if isinstance(message, types.CallbackQuery):
    #     message = message.message

    # start_msg = await message.answer(text=text,
    #                                 parse_mode='html',
    #                                 reply_markup=start_kb.as_markup(resize_keyboard=True,
    #                                                                 is_persistent=True))
    # if text_msg is None:
    #     await message.answer(text=start_text,
    #                          disable_web_page_preview=True)

    # text_msg = text_msg if text_msg else 'Главное меню'
    if not main_menu_msg or not is_callback:
        await bot.set_my_description(description='test22',
                                     language_code='ru')
        main_menu_msg: types.Message = await message.answer(start_text,
                                                            reply_markup=start_kb.as_markup(),
                                                            disable_web_page_preview=True,
                                                            disable_notification=True)
    else:
        chat_id, message_id = main_menu_msg

        main_menu_msg: types.Message = await bot.edit_message_text(text=start_text,
                                                                    chat_id=chat_id,
                                                                    message_id=message_id,
                                                                    disable_web_page_preview=True)

        await bot.edit_message_reply_markup(chat_id=chat_id,
                                            message_id=message_id,
                                            reply_markup=start_kb.as_markup())

    # msg_data = (main_menu_msg.chat.id, main_menu_msg.message_id)

    # await state.update_data(main_menu_msg=msg_data)
    
    # if main_menu_msg:
    #     try:
    #         await main_menu_msg.delete()
    #     except Exception:
    #         pass
    # await state.update_data(start_msg=start_msg.message_id)
    # await state.update_data(username=message.from_user.username)
    # try:
    #     await bot.delete_message(message.chat.id,
    #                             prev_start_msg)
    # except Exception:
    #     pass
    try:
        if not is_callback:
            await message.delete()
    except Exception:
        pass


@main_router.callback_query(F.data.startswith('swift'))
async def swift_confirm(callback: types.CallbackQuery,
                session: Session,
                state: FSMContext,
                bot: Bot,
                text_msg: str = None):
    print('inside')
    MODER_CHANNEL_ID = '-1002435890346'
    NEW_GROUP_ID = '-4667981929'

    message_text = callback.message.text
    message_id = callback.message.message_id

    print('MESSAGE TEXT', message_text)

    callback_data = callback.data.split('_')

    confirm_marker = callback_data[1]

    order_id = callback_data[-1]

    sub_text = '\n\n Ничего не произошло (вероятно пользователь заблокировал бота)😔'

    if confirm_marker == 'agree':
        CustomOrder = Base.classes.general_models_customorder
        Guest = Base.classes.general_models_guest

        query = (
            select(
                CustomOrder.id,
                Guest.tg_id,
            )\
            .join(Guest,
                CustomOrder.guest_id == Guest.tg_id)\
            .where(
                or_(
                    CustomOrder.id == order_id,
                    )
            )\
            .order_by(CustomOrder.time_create.asc())\
        )

        with session as session:
            res = session.execute(query)

            res = res.fetchall()

        _order_id, _guest_id = res[0]

        _url = f'https://api.moneyswap.online/test_swift_sepa?user_id={_guest_id}&order_id={_order_id}&order_status={confirm_marker}'
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession() as _session:
            async with _session.get(_url,
                                timeout=timeout) as response:
                response_json: dict = await response.json()
        
        print('response_json', response_json)
        _status = response_json.get('status')

        if _status == 'success':
            done_query = (
                update(
                    CustomOrder
                )\
                .values(moderation=True,
                        status='Завершен')\
                .where(CustomOrder.id == order_id)
            )
            session.execute(done_query)

            try:
                session.commit()
            except Exception as ex:
                session.rollback()
            else:
                sub_text = '\n\n<b><i>Заявка принята в работу✅</i></b>'

    elif confirm_marker == 'reject':
        sub_text = '\n\n<b><i>Заявка отклонена❌</i></b>'
        
        CustomOrder = Base.classes.general_models_customorder
        Guest = Base.classes.general_models_guest

        query = (
            select(
                CustomOrder.id,
                Guest.tg_id,
            )\
            .join(Guest,
                CustomOrder.guest_id == Guest.tg_id)\
            .where(
                or_(
                    CustomOrder.id == order_id,
                    )
            )\
            .order_by(CustomOrder.time_create.asc())\
        )

        with session as session:
            res = session.execute(query)

            res = res.fetchall()

        _order_id, _guest_id = res[0]

        _url = f'https://api.moneyswap.online/test_swift_sepa?user_id={_guest_id}&order_id={_order_id}&order_status={confirm_marker}'
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession() as _session:
            async with _session.get(_url,
                                timeout=timeout) as response:
                pass
        # pass
    
    new_message_text = message_text + sub_text

    # if _guest_id == 686339126:
    #     await bot.edit_message_text(text=new_message_text,
    #                                 chat_id=NEW_GROUP_ID,
    #                                 message_id=message_id,
    #                                 reply_markup=None,
    #                                 disable_web_page_preview=True)
    # else:
    try:
        await bot.edit_message_text(text=new_message_text,
                                    chat_id=MODER_CHANNEL_ID,
                                    message_id=message_id,
                                    reply_markup=None,
                                    disable_web_page_preview=True)
    except Exception as ex:
        print(ex)
        pass
    
    await callback.answer()


async def test_send(user_id: int,
                    order_id: int,
                    marker: str,
                    session: Session,
                    bot: Bot):
    MODER_CHANNEL_ID = '-1002435890346'
    _limit = 4

    CustomOrder = Base.classes.general_models_customorder
    Guest = Base.classes.general_models_guest

    if marker == 'swift/sepa':
        query = (
            select(
                CustomOrder,
                Guest,
            )\
            .join(Guest,
                CustomOrder.guest_id == Guest.tg_id)\
            .where(
                or_(
                    CustomOrder.id == order_id,
                    )
            )\
            .order_by(CustomOrder.time_create.asc())\
        )

        with session as session:
            res = session.execute(query)

            res = res.fetchall()

        # print(res)

        msg_text = '💰<b>Новая заявка Swift/Sepa, ожидающая модерации:</b>\n'

        for idx, _tuple in enumerate(res[:_limit], start=1):
            el, guest = _tuple
            chat_link = guest.chat_link
            # print(el.time_create)
            time_create = el.time_create.astimezone(moscow_tz).strftime('%d.%m.%Y %H:%M')
    #         el_form = f'''
    # Время создания: {time_create}\r
    # Тип заявки: {el.request_type}\r
    # Пользователь: {el.guest_id}\r
    # Комментарий: {el.comment}\r
    # Ссылка на заявку в <a href="https://api.moneyswap.online/django/admin/general_models/customorder/{el.id}/change/">django admin</a>
    # ''' 
            el_form = f'''
    Время создания: {time_create}\r
    Тип заявки: {el.request_type}\r
    Пользователь: {el.guest_id}\r
    Сумма: {el.amount}\r
    Комментарий: {el.comment}\r
    Ссылка на заявку в django admin👇🏼 \r
    https://api.moneyswap.online/django/admin/general_models/customorder/{el.id}/change/
    ''' 

            # print(el.__dict__)
            if chat_link:
                el_form += f'\rСсылка на чат по этому вопросу: {chat_link}\n'
            
            msg_text += f'\r{el_form}'
        
        try:
            # NEW_GROUP_ID = '-4667981929'
            
            _kb = create_confirm_swift_sepa_kb(order_id)
            # if guest.tg_id == 686339126:

            #     await bot.send_message(chat_id=NEW_GROUP_ID,
            #                            text=msg_text,
            #                            reply_markup=_kb.as_markup(),
            #                            disable_web_page_preview=True)
            # else:
            # if guest.tg_id == 686339126:
            #     _disable_notification = True
            # else:
            #     _disable_notification = False
            # else:
            await bot.send_message(chat_id=MODER_CHANNEL_ID,
                                    text=msg_text,
                                    reply_markup=_kb.as_markup(),
                                    disable_web_page_preview=True)
        except Exception as ex:
            print('Ошибка при отправке уведолмения в бота уведолмений')
            print(ex)
        # hidden_orders_count = len(res) - _limit

        # if hidden_orders_count > 0:
        #     msg_text += f'\n <b><i>* {hidden_orders_count} элементов не были показаны</i></b>'

    else:

        FeedbackForm = Base.classes.general_models_feedbackform

        query = (
            select(
                FeedbackForm
            )\
            .where(
                FeedbackForm.id == order_id,
            )
            .order_by(FeedbackForm.time_create.asc())\
        )
        with session as session:
            res = session.execute(query)

            res = res.scalars().all()
        
        # msg_text += '\n<b>Формы обратной связи, ожидающие модерации:</b>\n'
        # print(res, len(res))
        msg_text = '⏳<b>Новая заявка Форма обратной связи, ожидающая внимания:</b>\n'

        for idx, el in enumerate(res[:_limit], start=1):
            time_create = el.time_create.astimezone(moscow_tz).strftime('%d.%m.%Y %H:%M')
            el_form = f'''
    Время создания: {time_create}\r
    Тип проблемы: {el.reasons}\r
    Пользователь: {el.username}\r
    Ссылка на заявку в <a href="https://api.moneyswap.online/django/admin/general_models/feedbackform/{el.id}/change/">django admin</a>
    ''' 

            msg_text += f'\r{el_form}'

        # hidden_orders_count = len(res) - _limit

        # if hidden_orders_count > 0:
        #     msg_text += f'\n <b><i>* {hidden_orders_count} элементов не были показаны</i></b>'

        try:
            await bot.send_message(chat_id=MODER_CHANNEL_ID,
                                text=msg_text,
                                disable_web_page_preview=True)
        except Exception as ex:
            print('Ошибка при отправке уведолмения в бота уведолмений')
            print(ex)


async def send_review(review_id: int,
                      session: Session,
                      bot: Bot):
    MODER_CHANNEL_ID = '-1002435890346'

    Review = Base.classes.general_models_newbasereview

    # if marker == 'both':
    #     marker = 'no_cash'

    # match marker:
    #     case 'no_cash':
    #         Review = Base.classes.no_cash_review
    #         admin_page = 'no_cash'
    #     case 'cash':
    #         Review = Base.classes.cash_review
    #         admin_page = 'cash'
    #     case 'partner':
    #         Review = Base.classes.partners_review
    #         admin_page = 'partners'
    
    query = (
        select(
            Review
        )\
        .where(
            Review.id == review_id
            )
    )

    res = session.execute(query)

    review = res.scalar_one_or_none()

    if review:
        msg_text = '📝<b>Новый отзыв, ожидающий модерации:</b>\n\n'
        time_create = review.time_create.astimezone(moscow_tz).strftime('%d.%m.%Y %H:%M')

        review_form = f'''
    Время создания: {time_create}\r
    
    Ссылка на заявку в django admin👇🏼\r
    https://api.moneyswap.online/django/admin/general_models/newbasereview/{review_id}/change/
    '''
        msg_text += review_form

        await bot.send_message(chat_id=MODER_CHANNEL_ID,
                               text=msg_text)
        

async def send_comment(comment_id: int,
                      session: Session,
                      bot: Bot):
    MODER_CHANNEL_ID = '-1002435890346'

    Comment = Base.classes.general_models_newbasecomment
    Review = Base.classes.general_models_newbasereview

    # if marker == 'both':
    #     marker = 'no_cash'

    # match marker:
    #     case 'no_cash':
    #         Comment = Base.classes.no_cash_comment
    #         Exchange = Base.classes.no_cash_exchange
    #         Review = Base.classes.no_cash_review
    #         admin_page = 'no_cash'
    #     case 'cash':
    #         Comment = Base.classes.cash_comment
    #         Exchange = Base.classes.cash_exchange
    #         Review = Base.classes.cash_review
    #         admin_page = 'cash'
    #     case 'partner':
    #         Comment = Base.classes.partners_comment
    #         Exchange = Base.classes.partners_exchange
    #         Review = Base.classes.partners_review
    #         admin_page = 'partners'
    
    query = (
        select(
            Comment,
            Review,
        )\
        .join(Review,
              Comment.review_id == Review.id)\
        .where(Comment.id == comment_id)
    )

    res = session.execute(query)

    res_comment = res.fetchall()

    if res_comment:
        comment, review = res_comment[0]

        ExchangeAdmin = Base.classes.general_models_exchangeadmin

        check_on_admin_query = (
            select(
                ExchangeAdmin.exchange_name
            )\
            .where(
                and_(
                    ExchangeAdmin.user_id == comment.guest_id,
                    ExchangeAdmin.exchange_name == review.exchange_name,
                )
            )
        )

        res = session.execute(check_on_admin_query)

        admin_res = res.fetchall()

        if admin_res:
            admin_res = admin_res[0][0]
            sub_text = f'комментарий администрации на обменник {admin_res}'
        else:
            sub_text = f'комментарий'

        msg_text = f'📝<b>Новый {sub_text}, ожидающий модерации:</b>\n\n'
        time_create = comment.time_create.astimezone(moscow_tz).strftime('%d.%m.%Y %H:%M')

        comment_form = f'''
    Время создания: {time_create}\r
    
    Ссылка на заявку в django admin👇🏼\r
    https://api.moneyswap.online/django/admin/general_models/newbasecomment/{comment.id}/change/
    '''
        msg_text += comment_form

        await bot.send_message(chat_id=MODER_CHANNEL_ID,
                               text=msg_text)


async def result_chat_link(result_text: str,
                           bot: Bot):
    MODER_CHANNEL_ID = '-1002435890346'
    # DEV_ID = 686339126

    try:
        await bot.send_message(chat_id=MODER_CHANNEL_ID,
                               text=result_text)
    except Exception as ex:
        print('Ошибка при отправке уведолмения в бота уведолмений')
        print(ex)


async def test_result_chat_link(result_text: str,
                                bot: Bot):
    # MODER_CHANNEL_ID = '-1002435890346'
    # DEV_ID = 686339126
    NEW_GROUP_ID = '-4667981929'

    try:
        await bot.send_message(chat_id=NEW_GROUP_ID,
                               text=result_text)
    except Exception as ex:
        print('Ошибка при отправке уведолмения в бота уведолмений')
        print(ex)


async def test_send_info(execute_time,
                    start_users_count: int,
                    end_users_count: int,
                    session: Session,
                    bot: Bot):
    MODER_CHANNEL_ID = '-1002435890346'

    msg_text = f'Массовая рассылка завершена\n\nВремя выполнения: {execute_time}\n\nНачальное число активных пользователей: {start_users_count}\n\Конечное число активных пользователей: {end_users_count}'

    await bot.send_message(chat_id=MODER_CHANNEL_ID,
                           text=msg_text,
                           disable_web_page_preview=True)




@main_router.message(Command('test'))
async def test(message: types.Message | types.CallbackQuery,
                session: Session,
                state: FSMContext,
                bot: Bot,
                text_msg: str = None):
    MODER_CHANNEL_ID = '-1002435890346'
    _limit = 4

    DB_DATA = Base.classes.general_models_customorder
    Guest = Base.classes.general_models_guest

    query = (
        select(
            DB_DATA,
            Guest,
        )\
        .join(Guest,
              DB_DATA.guest_id == Guest.tg_id)\
        .order_by(DB_DATA.time_create.asc())\
    )

    res = session.execute(query)

    res = res.fetchall()

    # print(res)

    msg_text = '<b>Заявки Swift/Sepa, ожидающие модерации:</b>\n'

    for idx, _tuple in enumerate(res[:_limit], start=1):
        el, guest = _tuple
        chat_link = guest.chat_link
        time_create = el.time_create.astimezone().strftime('%d.%m.%Y %H:%M')
        el_form = f'''
{idx}
Время создания: {time_create}\r
Тип заявки: {el.request_type}\r
Пользователь: {el.guest_id}\r
Ссылка на заявку в <a href="https://api.moneyswap.online/django/admin/general_models/customorder/{el.id}/change/">django admin</a>
''' 
        # print(el.__dict__)
        if chat_link:
            el_form += f'\rСсылка на чат по этому вопросу: {chat_link}\n'
        
        msg_text += f'\r{el_form}'
    
    hidden_orders_count = len(res) - _limit

    if hidden_orders_count > 0:
        msg_text += f'\n <b><i>* {hidden_orders_count} элементов не были показаны</i></b>'

    FeedbackForm = Base.classes.general_models_feedbackform

    query = (
        select(
            FeedbackForm
        )\
        .order_by(FeedbackForm.time_create.asc())\
    )

    res = session.execute(query)

    res = res.scalars().all()
    
    msg_text += '\n<b>Формы обратной связи, ожидающие модерации:</b>\n'

    for idx, el in enumerate(res[:_limit], start=1):
        time_create = el.time_create.astimezone().strftime('%d.%m.%Y %H:%M')
        el_form = f'''
{idx}
Время создания: {time_create}\r
Тип проблемы: {el.reasons}\r
Пользователь: {el.username}\r
Ссылка на заявку в <a href="https://api.moneyswap.online/django/admin/general_models/feedbackform/{el.id}/change/">django admin</a>
''' 

        msg_text += f'\r{el_form}'

    hidden_orders_count = len(res) - _limit

    if hidden_orders_count:
        msg_text += f'\n <b><i>* {hidden_orders_count} элементов не были показаны</i></b>'


    await bot.send_message(chat_id=MODER_CHANNEL_ID,
                           text=msg_text,
                           disable_web_page_preview=True)

# @main_router.message(F.text == 'Swift/Sepa')
# async def start_swift_sepa(message: types.Message,
#                            state: FSMContext,
#                            bot: Bot):
#     data = await state.get_data()
#     await state.set_state(SwiftSepaStates.request_type)
#     await state.update_data(order=dict())

#     swift_start_kb = create_swift_start_kb()
#     kb = add_cancel_btn_to_kb(swift_start_kb)

#     main_menu_msg: tuple[str,str] = data.get('main_menu_msg')

#     # print('has_main_menu_msg?', bool(main_menu_msg))

#     if main_menu_msg:
#         try:
#             await bot.delete_message(*main_menu_msg)
#             # await main_menu_msg.delete()
#         except Exception:
#             pass

#     state_msg = await message.answer('<b>Выберите тип заявки</b>',
#                          reply_markup=kb.as_markup())
    
#     state_data_message = (state_msg.chat.id, state_msg.message_id)
    
#     await state.update_data(state_msg=state_data_message)
#     # await state.update_data(username=message.from_user.username)
#     await message.delete()


@main_router.callback_query(F.data.in_(('cancel', 'to_main')))
async def back_to_main(callback: types.CallbackQuery,
                       state: FSMContext,
                       session: Session,
                       bot: Bot):
    data = await state.get_data()
    # start_msg = state_data.get('start_msg')
    # main_menu_msg: tuple[str,str] = data.get('main_menu_msg')
    chat_link_msg: tuple[str,str] = data.get('chat_link_msg')

    await state.clear()

    # if main_menu_msg:
    #     await state.update_data(main_menu_msg=main_menu_msg)

    if chat_link_msg:
        await state.update_data(chat_link_msg=chat_link_msg)

    await start(callback,
                session,
                state,
                bot,
                text_msg='Главное меню')
    try:
        await callback.answer()
        await callback.message.delete()
    except Exception:
        pass


@main_router.callback_query(F.data == 'invoice_swift/sepa')
async def invoice_swift_sepa(callback: types.CallbackQuery,
                            session: Session,
                            state: FSMContext,
                            bot: Bot,
                            api_client: Client):
    data = await state.get_data()

    main_menu_msg: tuple[str,str] = data.get('main_menu_msg')

    chat_id, message_id = main_menu_msg

    swift_sepa_kb = create_swift_sepa_kb()
    swift_sepa_kb = add_cancel_btn_to_kb(swift_sepa_kb)

    await bot.edit_message_text(text='Выберите действие',
                                chat_id=chat_id,
                                message_id=message_id)
    
    await bot.edit_message_reply_markup(chat_id=chat_id,
                                        message_id=message_id,
                                        reply_markup=swift_sepa_kb.as_markup())
    
    await callback.answer()
    

@main_router.callback_query(F.data == 'start_swift_sepa')
async def start_swift_sepa(callback: types.CallbackQuery,
                            session: Session,
                            state: FSMContext,
                            bot: Bot,
                            api_client: Client):
    await callback.answer(text='Находится в разработке',
                          show_alert=True)


@main_router.callback_query(F.data == 'conditions')
async def get_conditions(callback: types.CallbackQuery,
                        session: Session,
                        state: FSMContext,
                        bot: Bot,
                        api_client: Client):
    await callback.answer(text='Находится в разработке',
                          show_alert=True)
    

@main_router.callback_query(F.data == 'about')
async def get_about(callback: types.CallbackQuery,
                    session: Session,
                    state: FSMContext,
                    bot: Bot,
                    api_client: Client):
    await callback.answer(text='Находится в разработке',
                          show_alert=True)



@main_router.callback_query(F.data == 'support')
async def start_support(callback: types.CallbackQuery,
                        session: Session,
                        state: FSMContext,
                        bot: Bot,
                        api_client: Client):
    data = await state.get_data()

    main_menu_msg: tuple[str,str] = data.get('main_menu_msg')

    chat_id, message_id = main_menu_msg

    support_kb = create_support_kb()
    support_kb = add_cancel_btn_to_kb(support_kb)

    await bot.edit_message_text(text='Выберите действие',
                                chat_id=chat_id,
                                message_id=message_id)
    
    await bot.edit_message_reply_markup(chat_id=chat_id,
                                        message_id=message_id,
                                        reply_markup=support_kb.as_markup())
    
    await callback.answer()
    

@main_router.callback_query(F.data == 'feedback_form')
async def start_support(callback: types.CallbackQuery,
                        session: Session,
                        state: FSMContext,
                        bot: Bot,
                        api_client: Client):
    data = await state.get_data()

    main_menu_msg: tuple[str,str] = data.get('main_menu_msg')

    chat_id, message_id = main_menu_msg

    await state.set_state(FeedbackFormStates.reason)

    await state.update_data(feedback_form=dict())

    reason_kb = create_feedback_form_reasons_kb()

    reason_kb = add_cancel_btn_to_kb(reason_kb)

    await bot.edit_message_text(text='Выберите причину обращения',
                                chat_id=chat_id,
                                message_id=message_id)

    await bot.edit_message_reply_markup(reply_markup=reason_kb.as_markup(),
                                        chat_id=chat_id,
                                        message_id=message_id)
    
    await callback.answer()


@main_router.callback_query(F.data == 'feedback_form_send')
async def feedback_form_send(callback: types.CallbackQuery,
                            session: Session,
                            state: FSMContext,
                            bot: Bot,
                            api_client: Client):
    data = await state.get_data()

    # main_menu_msg: tuple[str,str] = data.get('main_menu_msg')

    # chat_id, message_id = main_menu_msg

    feedback_form = data.get('feedback_form')

    feedback_values = {
        'reasons': reason_dict.get(feedback_form['reason']),
        'username': feedback_form['username'],
        'email': feedback_form['contact'],
        'description': feedback_form['description'],
        'time_create': datetime.now(),
    }

    FeedbackForm = Base.classes.general_models_feedbackform

    session.execute(insert(FeedbackForm).values(feedback_values))
    try:
        session.commit()

        _text = 'Обращение успешно отправлено!'
    except Exception as ex:
        print(ex)
        session.rollback()
        _text = 'Что то пошло не так, попробуйте повторить позже'
    
    finally:
        await callback.answer(text=_text,
                              show_alert=True)
        
        await start(callback,
                    session,
                    state,
                    bot,
                    text_msg='Главное меню')

    
@main_router.callback_query(F.data.startswith(FEEDBACK_REASON_PREFIX))
async def request_type_state(callback: types.CallbackQuery,
                             session: Session,
                             state: FSMContext,
                             bot: Bot):
    reason = callback.data.split('__')[-1]

    data = await state.get_data()

    main_menu_msg: tuple[str,str] = data.get('main_menu_msg')

    chat_id, message_id = main_menu_msg

    feedback_form = data.get('feedback_form')

    feedback_form['reason'] = reason

    await state.update_data(feedback_form=feedback_form)

    await state.set_state(FeedbackFormStates.description)


    await bot.edit_message_text(text='Опишите проблему, если это нужно\nЕсли нет напишите "Нет"',
                                chat_id=chat_id,
                                message_id=message_id)
    
    kb = add_cancel_btn_to_kb()

    await bot.edit_message_reply_markup(chat_id=chat_id,
                                        message_id=message_id,
                                        reply_markup=kb.as_markup())
    
    await callback.answer()


@main_router.message(FeedbackFormStates.description)
async def request_type_state(message: types.Message,
                             session: Session,
                             state: FSMContext,
                             bot: Bot):
    # reason = callback.data.split('__')[-1]
    description = message.text

    data = await state.get_data()

    main_menu_msg: tuple[str,str] = data.get('main_menu_msg')

    chat_id, message_id = main_menu_msg

    feedback_form = data.get('feedback_form')

    feedback_form['description'] = description

    await state.update_data(feedback_form=feedback_form)

    await state.set_state(FeedbackFormStates.contact)

    await bot.edit_message_text(text='Укажите контактные данные, по которым мы сможем с Вами связаться\n(E-mail, ссылка на Телеграм или что то другое)',
                                chat_id=chat_id,
                                message_id=message_id)
    
    kb = add_cancel_btn_to_kb()

    await bot.edit_message_reply_markup(chat_id=chat_id,
                                        message_id=message_id,
                                        reply_markup=kb.as_markup())
    
    await message.delete()
    

@main_router.message(FeedbackFormStates.contact)
async def country_state(message: types.Message,
                        session: Session,
                        state: FSMContext,
                        bot: Bot):
    contact = message.text

    data = await state.get_data()

    main_menu_msg: tuple[str,str] = data.get('main_menu_msg')

    chat_id, message_id = main_menu_msg

    feedback_form = data.get('feedback_form')

    feedback_form['contact'] = contact

    await state.update_data(feedback_form=feedback_form)

    await state.set_state(FeedbackFormStates.username)

    await bot.edit_message_text(text='Укажите имя, чтобы мы знали как к Вам обращаться',
                                chat_id=chat_id,
                                message_id=message_id)
    
    kb = add_cancel_btn_to_kb()

    await bot.edit_message_reply_markup(chat_id=chat_id,
                                        message_id=message_id,
                                        reply_markup=kb.as_markup())

    await message.delete()
    


@main_router.message(FeedbackFormStates.username)
async def country_state(message: types.Message,
                        session: Session,
                        state: FSMContext,
                        bot: Bot):
    username = message.text

    data = await state.get_data()

    main_menu_msg: tuple[str,str] = data.get('main_menu_msg')

    chat_id, message_id = main_menu_msg

    feedback_form = data.get('feedback_form')

    feedback_form['username'] = username

    await state.update_data(feedback_form=feedback_form)

    feedback_confirm_kb = create_feedback_confirm_kb()

    feedback_confirm_kb = add_cancel_btn_to_kb(feedback_confirm_kb)

    await bot.edit_message_text(text='Заполнение завершено\nВыберите действие',
                                chat_id=chat_id,
                                message_id=message_id)

    await bot.edit_message_reply_markup(chat_id=chat_id,
                                        message_id=message_id,
                                        reply_markup=feedback_confirm_kb.as_markup())

    await message.delete()

    # feedback_values = {
    #     'reasons': reason_dict.get(feedback_form['reason']),
    #     'username': username,
    #     'email': feedback_form['contact'],
    #     'description': feedback_form['description'],
    #     'time_create': datetime.now(),
    # }

    # FeedbackForm = Base.classes.general_models_feedbackform

    # session.execute(insert(FeedbackForm).values(feedback_values))
    # try:
    #     session.commit()

    #     tx = ''
    # except Exception as ex:
    #     print(ex)


# @main_router.message(FeedbackFormStates.username)
# async def country_state(message: types.Message,
#                         session: Session,
#                         state: FSMContext,
#                         bot: Bot):
#     username = message.text

#     data = await state.get_data()

#     main_menu_msg: tuple[str,str] = data.get('main_menu_msg')

#     chat_id, message_id = main_menu_msg

#     feedback_form = data.get('feedback_form')

#     feedback_form['username'] = username

#     feedback_values = {
#         'reasons': reason_dict.get(feedback_form['reason']),
#         'username': username,
#         'email': feedback_form['contact'],
#         'description': feedback_form['description'],
#         'time_create': datetime.now(),
#     }

#     FeedbackForm = Base.classes.general_models_feedbackform

#     session.execute(insert(FeedbackForm).values(feedback_values))
#     try:
#         session.commit()

#         tx = ''
#     except Exception as ex:
#         print(ex)


    # await state.update_data(feedback_form=feedback_form)

    # await state.set_state(FeedbackFormStates.username)

    # await bot.edit_message_text(text='Укажите имя, чтобы мы знали как к Вам обращаться',
    #                             chat_id=chat_id,
    #                             message_id=message_id)






@main_router.callback_query(F.data == 'send_app')
async def send_app(callback: types.CallbackQuery,
                   session: Session,
                   state: FSMContext,
                   bot: Bot,
                   api_client: Client):
    
    data = await state.get_data()
    order: dict = data.get('order')
    time_create = datetime.now()
    order.update({'guest_id': callback.from_user.id,
                  'time_create': time_create})
    # if order:
    print('order', order)

    state_process = data.get('state_process')
    state_msg: tuple[str, str] = data.get('state_msg')
    # state_msg: types.Message = data.get('state_msg')

    username = callback.message.from_user.username
    username_from_callback = callback.from_user.username

    kb = create_start_keyboard(callback.from_user.id)

    Order = Base.classes.general_models_customorder

    session.execute(insert(Order).values(order))
    session.commit()

    Guest = Base.classes.general_models_guest

    guest = session.query(Guest)\
                    .where(Guest.tg_id == callback.from_user.id)\
                    .first()
    
    chat_link = guest.chat_link
    
    
    if chat_link is None:
        print('делаю пост запрос')

        body = f'''"tg_id": {order['guest_id']}, "type": "{order['request_type']}", "country": "{order['country']}", "sum": "{order['amount']}", "comment": "{order['comment']}", "time_create": {order['time_create'].timestamp()}'''

        json_order = {
            "order": '{' + body + '}'
        }

        json_order = json.dumps(json_order,
                                ensure_ascii=False)

        print('json', json_order)

        #
        async with aiohttp.ClientSession() as aiosession:
            response = await aiosession.post(url='https://api.moneyport.pro/api/partners/create-order',
                                          data=json_order,
                                          headers={'Authorization': f'Bearer {BEARER_TOKEN}',
                                                   'CONTENT-TYPE': 'application/json'})
            response_json = await response.json()
            print(type(response_json))
            print(response_json)
            
            chat_link = response_json.get('chat')

            if chat_link is not None:
                chat_link = chat_link.get('url')

                session.execute(update(Guest)\
                                .where(Guest.tg_id == callback.from_user.id)\
                                .values(chat_link=chat_link))
                # guest.chat_link = chat_link
                session.commit()
            else:
                response_message = response_json.get('message')

                if response_message == 'Свободные чаты закончились.':
                    error_text = 'К сожалению, свободные чаты закончились. Попробуйте позже.'
                
                elif response_message == 'Для выполнения данной операции требуется войти в аккаунт.':
                    error_text = 'Сервис времмено не работает. Мы его уже чиним. Попробуйте позже.'
                    
                await callback.answer(text=error_text,
                                      show_alert=True)
                
                await start(callback.message,
                            session,
                            state,
                            bot,
                            text_msg='Главное меню')
                # await callback.message.answer('К сожалению, свободные чаты закончились. Попробуйте позже.',
                #                               reply_markup=kb.as_markup(resize_keyboard=True))
                try:
                    await bot.delete_message(*state_msg)
                    # await bot.delete_message(callback.from_user.id, state_msg.message_id)
                except Exception:
                    pass

                return
            # chat_link = json.dumps(response_json).get('chat').get('url')
            # print('ответ на запрос', chat_link)
    else:
        print('ссылка из базы', guest.chat_link)

        #

    # async with api_client as app:
    #     super_group = await app.create_supergroup(title=f'HelpChat|{callback.from_user.username}')
    #     chat_link = await app.create_chat_invite_link(super_group.id,
    #                                                   name=f'HelpChat|{username}')
    #     #
    #     is_add = await app.add_chat_members(chat_id=super_group.id,
    #                                           user_ids=[username_from_callback])

        # if state_process is not None:
        #     await app.send_message(chat_link,
        #                            state_process)

    # await bot.send_message(chat_link,
    #                        state_process)

    await callback.answer(text='Ваша заявка успешно отправлена!',
                          show_alert=True)
    
    if prev_chat_link_msg := data.get('chat_link_msg'):
        prev_chat_link_msg: tuple[str, str]
        try:
            await bot.delete_message(*prev_chat_link_msg)
            # await bot.delete_message(callback.from_user.id,
            #                          prev_chat_link_msg.message_id)
        except Exception:
            pass

    chat_link_msg = await callback.message.answer(f'Ссылка на чат по Вашему обращению -> {chat_link}',
                                                  reply_markup=kb.as_markup(resize_keyboard=True,
                                                                            is_persistent=True))
    message_data_for_delete = (callback.from_user.id, chat_link_msg.message_id)
    
    await state.update_data(chat_link_msg=message_data_for_delete)
    
    
    # await callback.message.answer(f'Ссылка на чат по Вашему обращению -> {chat_link.invite_link}',
    #                               reply_markup=kb.as_markup(resize_keyboard=True,
    #                                                         is_persistent=True))
    try:
        await bot.delete_message(*state_msg)
        # await bot.delete_message(callback.from_user.id, state_msg.message_id)
    except Exception:
        pass


@main_router.callback_query(F.data.in_(('pay_payment', 'access_payment')))
async def request_type_state(callback: types.CallbackQuery,
                             session: Session,
                             state: FSMContext,
                             bot: Bot):
    data = await state.get_data()
    state_msg: tuple[str, str] = data.get('state_msg')
    chat_id, message_id = state_msg
    # state_msg: types.Message = data.get('state_msg')
    request_type = 'Оплатить платеж' if callback.data == 'pay_payment' else 'Принять платеж'
    state_process = f'Тип заявки: {request_type}'
    #
    order = data.get('order')
    order['request_type'] = request_type
    await state.update_data(order=order)
    #
    # username_from_state = data.get('username')
    # print(username_from_state)
    # #
    # print(callback.message.from_user.username)
    # print(callback.from_user.username)
    # await state.update_data(username=callback.message.from_user.username)
    #
    await state.update_data(state_process=state_process)
    # print(state_msg)
    await state.update_data(request_type=callback.data)

    await state.set_state(SwiftSepaStates.country)

    kb = add_cancel_btn_to_kb()

    #
    await bot.edit_message_text(f'{state_process}\n<b>Введите страну...</b>',
                                chat_id,
                                message_id,
                                reply_markup=kb.as_markup())
    #

    # await state_msg.edit_text(f'{state_process}\n<b>Введите страну...</b>',
    #                           reply_markup=kb.as_markup())
    try:
        await callback.answer()
    except Exception:
        pass
    # await callback.message.answer('Введите страну...')

    # await callback.message.delete()


@main_router.message(SwiftSepaStates.country)
async def country_state(message: types.Message,
                        session: Session,
                        state: FSMContext,
                        bot: Bot):
    data = await state.get_data()
    state_msg: tuple[str, str] = data.get('state_msg')
    chat_id, message_id = state_msg
    # state_msg: types.Message = data.get('state_msg')
    await state.update_data(country=message.text)

    #
    order = data.get('order')
    order['country'] = message.text
    await state.update_data(order=order)
    #

    state_process = data.get('state_process')
    state_process += f'\nСтрана: {message.text}'
    await state.update_data(state_process=state_process)

    await state.set_state(SwiftSepaStates.amount)

    kb = add_cancel_btn_to_kb()

    #
    await bot.edit_message_text(f'{state_process}\n<b>Введите сумму...</b>',
                                chat_id,
                                message_id,
                                reply_markup=kb.as_markup())
    #

    # await state_msg.edit_text(f'{state_process}\n<b>Введите сумму...</b>',
    #                           reply_markup=kb.as_markup())
    # await message.answer('Введите сумму...')

    await message.delete()


@main_router.message(SwiftSepaStates.amount)
async def amount_state(message: types.Message,
                       session: Session,
                       state: FSMContext,
                       bot: Bot):
    data = await state.get_data()
    # state_msg: types.Message = data.get('state_msg')
    state_msg: tuple[str, str] = data.get('state_msg')
    chat_id, message_id = state_msg

    await state.update_data(amount=message.text)

    #
    order = data.get('order')
    order['amount'] = message.text
    await state.update_data(order=order)
    #

    state_process = data.get('state_process')
    state_process += f'\nСумма: {message.text}'
    await state.update_data(state_process=state_process)

    await state.set_state(SwiftSepaStates.task_text)

    kb = add_cancel_btn_to_kb()

    #
    await bot.edit_message_text(f'{state_process}\n<b>Опишите задачу, чтобы менеджеры могли быстрее все понять и оперативно начать выполнение...</b>',
                                chat_id,
                                message_id,
                                reply_markup=kb.as_markup())
    #

    # await state_msg.edit_text(f'{state_process}\n<b>Опишите задачу, чтобы менеджеры могли быстрее все понять и оперативно начать выполнение...</b>',
    #                           reply_markup=kb.as_markup())
    # await message.answer('Напишите подробности операции...')

    await message.delete()


@main_router.message(SwiftSepaStates.task_text)
async def task_text_state(message: types.Message,
                          session: Session,
                          state: FSMContext,
                          bot: Bot,
                          api_client: Client):
    data = await state.get_data()
    # state_msg: types.Message = data.get('state_msg')
    state_msg: tuple[str, str] = data.get('state_msg')
    chat_id, message_id = state_msg

    await state.update_data(task_text=message.text)

    #
    order = data.get('order')
    order['comment'] = message.text
    await state.update_data(order=order)
    #

    state_process = data.get('state_process')
    state_process += f'\nКомментарий: {message.text}'
    await state.update_data(state_process=state_process)

    # preview_response_text = await swift_sepa_data(state)

    kb = create_kb_to_main()

    # async with api_client as app:
    #     channel = await app.create_channel(title='Test111')
    #     chat_link = await app.create_chat_invite_link(channel.id)

    # print(channel)
    # print(channel.__dict__)
    # print(chat_link.invite_link)


    # chat_link = await bot.create_chat_invite_link(chat_id=channel.id,
    #                                   name='test_link')
    
    # await message.answer(text=chat_link.invite_link)

    #
    await bot.edit_message_text(f'{state_process}\n<b>Заполнение окончено.</b>',
                                chat_id,
                                message_id,
                                reply_markup=kb.as_markup())
    #

    # await state_msg.edit_text(f'{state_process}\n<b>Заполнение окончено.</b>',
    #                           reply_markup=kb.as_markup())
    # await message.answer(f'Ваша заявка:\n{preview_response_text}',
    #                      reply_markup=kb.as_markup())
    
    await message.delete()


@main_router.message(Command('send'))
async def send(message: types.Message,
               session: Session,
               bot: Bot):
    MassSendMessage = Base.classes.general_models_masssendmessage

    mass_message = session.query(MassSendMessage).options(joinedload(MassSendMessage.general_models_masssendimage_collection),
                                                      joinedload(MassSendMessage.general_models_masssendvideo_collection)).first()

    print(mass_message.general_models_masssendimage_collection)
    for q in mass_message.general_models_masssendimage_collection:
        print(q.__dict__)
    print(mass_message.general_models_masssendvideo_collection)
    for w in mass_message.general_models_masssendvideo_collection:
        print(w.__dict__)

    await try_add_file_ids_to_db(message,
                                 session,
                                 bot,
                                 mass_message)
    
    # session.refresh(mass_message)
    session.expire_all()

    print('22')
    for q in mass_message.general_models_masssendimage_collection:
        print(q.__dict__)
    print(mass_message.general_models_masssendvideo_collection)
    for w in mass_message.general_models_masssendvideo_collection:
        print(w.__dict__)

    # print(MassSendMessage)
    # print(MassSendMessage.__dict__)

    # os_path = os.path.dirname(os.path.abspath(__file__))

    # print(os_path)

    # valutes = session.query(Valutes).all()
    # messages = session.query(MassSendMessage).all()
    # MassSendImage = Base.classes.general_models_masssendimage
    # images = session.query(MassSendImage).all()

    # mass_message = session.query(MassSendMessage).options(joinedload(MassSendMessage.general_models_masssendimage_collection),
    #                                                   joinedload(MassSendMessage.general_models_masssendvideo_collection)).first()
   
    # for m in messages:
    #     # images = select(MassSendMessage).options(joinedload(MassSendMessage.images))
    #     # print(v.__dict__)
    #     # for i in m.general_models_masssendimage_collection:
    #     #     print(i.__dict__)
    #     images = [(image.id, image.file_id, types.InputMediaPhoto(media=types.FSInputFile(path=f'/home/skxnny/web/backup_bestexchange/django_fastapi/media/{image.image}'))) for image in m.general_models_masssendimage_collection]
    #     update_image_list = []
    #     for image in images:
    #         if image[1] is None:
    #             # upload image to telegram server
    #             loaded_image = await message.answer_photo(image[-1].media)
    #             # delete image message from chat
    #             await bot.delete_message(message.chat.id, message.message_id)
    #             image_file_id = loaded_image.photo[0].file_id
    #             print(image[0], image_file_id)
    #             image_dict = {
    #                 'id': image[0],
    #                 'file_id': image_file_id,
    #             }
    #             update_image_list.append(image_dict)
    #         else:
    #             print('из БД', image[1])
    #     if update_image_list:
    #         session.bulk_update_mappings(
    #             MassSendImage,
    #             update_image_list,
    #         )
    #         session.commit()
    #         session.flush(MassSendMessage.general_models_masssendimage_collection)
    mass_message_text: str = mass_message.content
    print(mass_message_text)
    mass_message_text: str = mass_message_text.replace('<p>','')\
                                                .replace('</p>', '\n')\
                                                .replace('<br>', '')\
                                                .replace('<p class="">', '')\
                                                # .replace('<span', '<span class="tg-spoiler"')

    print(mass_message_text)

    images = [types.InputMediaPhoto(media=image.file_id) for image in mass_message.general_models_masssendimage_collection]
    videos = [types.InputMediaVideo(media=video.file_id) for video in mass_message.general_models_masssendvideo_collection]
    mb = MediaGroupBuilder(images+videos, caption=mass_message_text)
    
    files = [types.InputMediaDocument(media=file.file_id) for file in mass_message.general_models_masssendfile_collection]
    mb_files = MediaGroupBuilder(files)
    # mb.build()
        # for image in m.general_models_masssendimage_collection:
        #     if image.file_id is None:

        #     image_id = await message.answer_photo(image.media)
        #     print(image_id)
        #     print('ID',image_id.photo[0].file_id)
        # images = [types.InputMediaPhoto(media=f'http://localhost:8000/django/media/{image.image}') for image in m.general_models_masssendimage_collection]
        # print(images)
        # videos = [types.InputMediaVideo(media=types.FSInputFile(path=f'/home/skxnny/web/backup_bestexchange/django_fastapi/media/{video.video}')) for video in m.general_models_masssendvideo_collection]
        # for v in videos:
            # await message.answer_video(v.media)
            # video_id = await message.answer_video('BAACAgIAAxkDAAOTZl79M00aHNBaYsc4gNk6znwWiQ4AAhFPAALje_hKCvWrvLSuzxY1BA')
            # print(video_id)
            # print('ID',video_id.video.file_id)
        # videos = [types.InputMediaVideo(media=video.video) for video in m.general_models_masssendvideo_collection]
        # print(videos)

    # await message.answer_photo('https://img.freepik.com/free-photo/view-of-3d-adorable-cat-with-fluffy-clouds_23-2151113419.jpg')
    
    await message.answer_media_group(media=mb.build())
    await message.answer_media_group(media=mb_files.build())
    


# @main_router.message(F.video)
# async def add_photo(message: types.Message,
#                     session: Session,
#                     bot: Bot):
#     video = message.video
#     MassSendVideo = Base.classes.general_models_masssendvideo

#     session.execute(insert(MassSendVideo).values({'file_id': video.file_id,
#                                                   'video': video.file_name,
#                                                   'messsage_id': 1}))
#     session.commit()

#     await message.delete()


async def send_mass_message(bot: Bot,
                            session: Session,
                            name_send: str):
        with session as session:
            Guest = Base.classes.general_models_guest
            # session: Session

            # get MassSendMessage model from DB
            MassSendMessage = Base.classes.general_models_masssendmessage
            # mass_message = session.query(MassSendMessage)\
            #                         .options(joinedload(MassSendMessage.general_models_masssendimage_collection),
            #                                  joinedload(MassSendMessage.general_models_masssendvideo_collection))\
            #                         .first()
            mass_message = session.query(MassSendMessage)\
                                    .options(joinedload(MassSendMessage.general_models_masssendimage_collection),
                                             joinedload(MassSendMessage.general_models_masssendvideo_collection))\
                                    .where(MassSendMessage.name == name_send).first()

            # try add file_id for each related file passed object
            await try_add_file_ids(bot, session, mass_message)
            # refresh all DB records
            session.expire_all()

            mass_message_text: str = mass_message.content
            print(mass_message_text)
            # validate content text
            mass_message_text: str = mass_message_text.replace('<p>','')\
                                                        .replace('</p>', '\n')\
                                                        .replace('<br>', '')\
                                                        .replace('<p class="">', '')\
                                                        # .replace('<span', '<span class="tg-spoiler"')

            print(mass_message_text)

            images = [types.InputMediaPhoto(media=image.file_id) for image in mass_message.general_models_masssendimage_collection]
            videos = [types.InputMediaVideo(media=video.file_id) for video in mass_message.general_models_masssendvideo_collection]

            image_video_group = None
            if list(images+videos):
                image_video_group = MediaGroupBuilder(images+videos, caption=mass_message_text)
            
            files = [types.InputMediaDocument(media=file.file_id) for file in mass_message.general_models_masssendfile_collection]
            file_group = None
            if files:
                file_group = MediaGroupBuilder(files)

            try:
                if image_video_group is not None:
                    mb1 = await bot.send_media_group('350016695', media=image_video_group.build())
                    print('MB1', mb1)
                else:
                    await bot.send_message('350016695',
                                           text=mass_message_text)
                if file_group is not None:
                    mb2 = await bot.send_media_group('350016695', media=file_group.build())    
                    print('MB2', mb2)
                guest = session.query(Guest).where(Guest.tg_id == '350016695').first()
                if not guest.is_active:
                   session.execute(update(Guest).where(Guest.tg_id == '350016695').values(is_active=True))
                   session.commit()
            except Exception:
                session.execute(update(Guest).where(Guest.tg_id == '350016695').values(is_active=False))
                session.commit()
            
            session.close()


@main_router.message()
async def ignore_any_message(message: types.Message):
    try:
        await message.delete()
    except Exception as ex:
        print(ex)