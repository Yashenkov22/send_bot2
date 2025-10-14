import pytz

import aiohttp

from aiogram import Router, types, Bot, F

from aiogram.filters import Command
from aiogram.fsm.context import FSMContext


from sqlalchemy import and_, insert, select, update, or_
from sqlalchemy.ext.asyncio import AsyncSession

from keyboards import (create_confirm_swift_sepa_kb)

from db.base import Base


main_router = Router()


moscow_tz = pytz.timezone('Europe/Moscow')

@main_router.message(Command('start'))
async def start(message: types.Message,
                session: AsyncSession,
                state: FSMContext,
                bot: Bot):
    await message.answer(text='Это бот для уведомлений')
    try:
        await message.delete()
    except Exception:
        pass


@main_router.callback_query(F.data.startswith('swift'))
async def swift_confirm(callback: types.CallbackQuery,
                session: AsyncSession,
                state: FSMContext,
                bot: Bot):
    print('inside')
    MODER_CHANNEL_ID = '-1002435890346'
    NEW_GROUP_ID = '-4667981929'

    message_text = callback.message.text
    message_id = callback.message.message_id

    print('MESSAGE TEXT', message_text)

    callback_data = callback.data.split('_')

    confirm_marker = callback_data[1]

    order_id = int(callback_data[-1])

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

        async with session as _session:
            res = await _session.execute(query)

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
            async with session as _session:
                await _session.execute(done_query)

                try:
                    await _session.commit()
                except Exception as ex:
                    await _session.rollback()
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

        async with session as _session:
            res = await _session.execute(query)

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
                    session: AsyncSession,
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

        async with session as _session:
            res = await _session.execute(query)

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
        async with session as _session:
            res = await _session.execute(query)

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
                      session: AsyncSession,
                      bot: Bot):
    MODER_CHANNEL_ID = '-1002435890346'

    Review = Base.classes.general_models_newbasereview
    
    query = (
        select(
            Review
        )\
        .where(
            Review.id == review_id
            )
    )
    async with session as _session:
        res = await _session.execute(query)

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
        

async def new_send_review(review_id: int,
                          session: AsyncSession,
                          bot: Bot):
    MODER_CHANNEL_ID = '-1002435890346'

    Review = Base.classes.general_models_review
    
    query = (
        select(
            Review
        )\
        .where(
            Review.id == review_id
            )
    )
    async with session as _session:
        res = await _session.execute(query)

        review = res.scalar_one_or_none()

    if review:
        msg_text = '📝<b>Новый отзыв, ожидающий модерации (редизайн):</b>\n\n'
        time_create = review.time_create.astimezone(moscow_tz).strftime('%d.%m.%Y %H:%M')

        review_form = f'''
    Время создания: {time_create}\r
    
    Ссылка на заявку в django admin👇🏼\r
    https://api.moneyswap.online/django/admin/general_models/review/{review_id}/change/
    '''
        msg_text += review_form

        await bot.send_message(chat_id=MODER_CHANNEL_ID,
                               text=msg_text)

        

async def send_comment(comment_id: int,
                      session: AsyncSession,
                      bot: Bot):
    MODER_CHANNEL_ID = '-1002435890346'

    Comment = Base.classes.general_models_newbasecomment
    Review = Base.classes.general_models_newbasereview
    
    query = (
        select(
            Comment,
            Review,
        )\
        .join(Review,
              Comment.review_id == Review.id)\
        .where(Comment.id == comment_id)
    )
    async with session as _session:
        res = await _session.execute(query)

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
        
        async with session as _session:
            res = await _session.execute(check_on_admin_query)

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
        

async def new_send_comment(comment_id: int,
                           session: AsyncSession,
                           bot: Bot):
    MODER_CHANNEL_ID = '-1002435890346'

    Comment = Base.classes.general_models_comment
    Review = Base.classes.general_models_review
    
    query = (
        select(
            Comment,
            Review,
        )\
        .join(Review,
              Comment.review_id == Review.id)\
        .where(Comment.id == comment_id)
    )
    async with session as _session:
        res = await _session.execute(query)

        res_comment = res.fetchall()

    if res_comment:
        comment, review = res_comment[0]

        ExchangeAdmin = Base.classes.general_models_newexchangeadmin
        Exchange = Base.classes.general_models_exchanger

        check_on_admin_query = (
            select(
                Exchange.name
            )\
            .select_from(ExchangeAdmin)\
            .join(Exchange,
                  ExchangeAdmin.exchange_id == Exchange.id)\
            .where(
                and_(
                    ExchangeAdmin.user_id == comment.guest_id,
                    ExchangeAdmin.exchange_id == review.exchange_id,
                )
            )
        )
        
        async with session as _session:
            res = await _session.execute(check_on_admin_query)

            admin_res = res.fetchall()

        if admin_res:
            admin_res = admin_res[0][0]
            sub_text = f'комментарий администрации на обменник {admin_res}'
        else:
            sub_text = f'комментарий'

        msg_text = f'📝<b>Новый {sub_text}, ожидающий модерации (редизайн):</b>\n\n'
        time_create = comment.time_create.astimezone(moscow_tz).strftime('%d.%m.%Y %H:%M')

        comment_form = f'''
    Время создания: {time_create}\r
    
    Ссылка на заявку в django admin👇🏼\r
    https://api.moneyswap.online/django/admin/general_models/comment/{comment.id}/change/
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
                    session: AsyncSession,
                    bot: Bot):
    MODER_CHANNEL_ID = '-1002435890346'

    msg_text = f'Массовая рассылка завершена\n\nВремя выполнения: {execute_time}\n\nНачальное число активных пользователей: {start_users_count}\n\nКонечное число активных пользователей: {end_users_count}'

    await bot.send_message(chat_id=MODER_CHANNEL_ID,
                           text=msg_text,
                           disable_web_page_preview=True)




@main_router.message(Command('test'))
async def test(message: types.Message | types.CallbackQuery,
                session: AsyncSession,
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

    res = await session.execute(query)

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

    res = await session.execute(query)

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


@main_router.message()
async def ignore_any_message(message: types.Message):
    try:
        await message.delete()
    except Exception as ex:
        print(ex)