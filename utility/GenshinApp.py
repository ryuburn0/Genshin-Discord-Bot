import asyncio
import json
import discord
import genshin
from datetime import datetime
from typing import Sequence, Union, Tuple
from .emoji import emoji
from .utils import log, getCharacterName, trimCookie, getServerName, getDayOfWeek,user_last_use_time
from .config import config

class GenshinApp:
    def __init__(self) -> None:
        try:
            with open('data/user_data.json', 'r', encoding="utf-8") as f:
                self.__user_data: dict[str, dict[str, str]] = json.load(f)
        except:
            self.__user_data: dict[str, dict[str, str]] = { }

    async def setCookie(self, user_id: str, cookie: str) -> str:
        """Set user cookie
        
        ------
        Parameters
        user_id `str`: User Discord ID
        cookie `str`: Hoyolab cookie
        ------
        Returns
        `str`: Reply to user
        """
        log.info(f'[instructions][{user_id}]setCookie: cookie={cookie}')
        user_id = str(user_id)
        cookie = trimCookie(cookie)
        if cookie == None:
            return f'Invalid Cookie，Please Re-Enter `/Cookie` to show description)'
        client = genshin.Client(lang='zh-tw')
        client.set_cookies(cookie)
        try:
            accounts = await client.genshin_accounts()
        except genshin.errors.GenshinException as e:
            log.info(f'[exception][{user_id}]setCookie: [retcode]{e.retcode} [exceptions]{e.original}')
            result = e.original
        else:
            if len(accounts) == 0:
                log.info(f'[UID][{user_id}]setCookie: There are no characters in this account')
                result = 'There are no characters in this account，Canceling Cookie setting'
            else:
                self.__user_data[user_id] = {}
                self.__user_data[user_id]['cookie'] = cookie
                log.info(f'[UID][{user_id}]setCookie: Cookie set successfully :D')
                
                if len(accounts) == 1 and len(str(accounts[0].uid)) == 9:
                    self.setUID(user_id, str(accounts[0].uid))
                    result = f'Cookie has been set, account UID: {accounts[0].uid} Saved！'
                else:
                    result = f'The cookie has been saved and is shared with your Hoyolab account{len(accounts)}Set Character\n Please use the command `/uid` to specify the Genshin Impact account to save'
                    self.__saveUserData()
        finally:
            return result

    async def getGameAccounts(self, user_id: str) -> Union[str, Sequence[genshin.models.GenshinAccount]]:
        """Get the Genshin account of each server under the same Hoyolab account

        ------
        Parameters
        user_id `str`: User Discord ID
        ------
        Returns
        `str | Sequence[genshin.models.GenshinAccount]`: When an exception occurs, the error message `str` is returned, and the query `Sequence[genshin.models.GenshinAccount]` result is returned under normal conditions. 
        """
        check, msg = self.checkUserData(user_id, checkUID=False)
        if check == False:
            return msg
        client = self.__getGenshinClient(user_id)
        try:
            accounts = await client.genshin_accounts()
        except genshin.GenshinException as e:
            log.info(f'[exception][{user_id}]getGameAccounts: [retcode]{e.retcode} [exceptions]{e.original}')
            return e.original
        except Exception as e:
            log.info(f'[exception][{user_id}]getGameAccounts: {e}')
            return str(e)
        else:
            return accounts
    
    def setUID(self, user_id: str, uid: str) -> str:
        """Save the specified UID

        ------
        Parameters
        user_id `str`: User Discord ID
        uid `str`: The UID to be saved.
        ------
        Returns
        `str`: Reply to user
        """
        log.info(f'[instruction][{user_id}]setUID: uid={uid}')
        self.__user_data[user_id]['uid'] = uid
        self.__saveUserData()
        return f'Account UID: {uid} set.'
    
    def getUID(self, user_id: str) -> Union[int, None]:
        if user_id in self.__user_data.keys():
            user_last_use_time.update(user_id)
            return int(self.__user_data[user_id].get('uid'))
        return None

    async def getRealtimeNote(self, user_id: str, *, schedule = False) -> Union[None, str, discord.Embed]:
        """Obtain User Stats (Resin, Realm Currency, Parameteric Transformer Reset, Expiditions, Dailies, Weeklies)
        
        ------
        Parameters
        user_id `str`: User Discord ID
        schedule `bool`: Whether to check resin for scheduling, when set to `True`, the instant note result will only be returned when the resin exceeds the set standard
        ------
        Returns
        `None | str | Embed`: When the resin is automatically checked, `None` is returned if it is not overflowing normally; an error message `str` is returned when an exception occurs, and the query result `discord.Embed` is returned under normal conditions.
        """
        if not schedule:
            log.info(f'[instruction][{user_id}]getRealtimeNote')
        check, msg = self.checkUserData(user_id, update_use_time=(not schedule))
        if check == False:
            return msg
   
        uid = self.__user_data[user_id]['uid']
        client = self.__getGenshinClient(user_id)
        try:
            notes = await client.get_genshin_notes(int(uid))
        except genshin.errors.DataNotPublic:
            log.info(f'[exception][{user_id}]getRealtimeNote: DataNotPublic')
            return 'The Real-Time Notes function is not enabled, please enable the Real-Time Notes function from the Hoyolab website ( https://www.hoyolab.com/setting/privacy ) or app first'
        except genshin.errors.InvalidCookies as e:
            log.info(f'[exception][{user_id}]getRealtimeNote: [retcode]{e.retcode} [exceptions]{e.original}')
            return 'Cookie Expired，Please Reset Cookie'
        except genshin.errors.GenshinException as e:
            log.info(f'[exception][{user_id}]getRealtimeNote: [retcode]{e.retcode} [exceptions]{e.original}')
            return e.original
        except Exception as e:
            log.error(f'[例外][{user_id}]getRealtimeNote: {e}')
            return str(e)
        else:
            if schedule == True and notes.current_resin < config.auto_check_resin_threshold:
                return None
            else:
                msg = f'{getServerName(uid[0])} {uid.replace(uid[3:-3], "***", 1)}\n'
                msg += f'--------------------\n'
                msg += self.__parseNotes(notes, shortForm=schedule)
                # According to the number of resins, with 80 as the dividing line, the embed color changes from green (0x28c828) to yellow (0xc8c828), and then to red (0xc82828)
                r = notes.current_resin
                color = 0x28c828 + 0x010000 * int(0xa0 * r / 80) if r < 80 else 0xc8c828 - 0x000100 * int(0xa0 * (r - 80) / 80)
                embed = discord.Embed(description=msg, color=color)
                return embed
    
    async def redeemCode(self, user_id: str, code: str) -> str:
        """Use the specified redemption code for the user

        ------
        Parameters
        user_id `str`: User Discord ID
        code `str`: Hoyolab Redemption Code
        ------
        Returns
        `str`:Reply to user
        """
        log.info(f'[instruction][{user_id}]redeemCode: code={code}')
        check, msg = self.checkUserData(user_id)
        if check == False:
            return msg
        client = self.__getGenshinClient(user_id)
        try:
            await client.redeem_code(code, int(self.__user_data[user_id]['uid']))
        except genshin.errors.GenshinException as e:
            log.info(f'[exception][{user_id}]redeemCode: [retcode]{e.retcode} [exceptions]{e.original}')
            result = e.original
        except Exception as e:
            log.error(f'[exception][{user_id}]redeemCode: [exceptions]{e}')
            result = f'{e}'
        else:
            result = f'Redemption Code {code} claimed successfully！'
        finally:
            return result
    
    async def claimDailyReward(self, user_id: str, *, honkai: bool = False, schedule = False) -> str:
        """Sign in for users at hoyolab

        ------
        Parameters
        user_id `str`: User Discord ID
        honkai `bool`: Also sign into Honkai Impact 3?
        schedule `bool`: Whether to check in automatically for the schedule
        ------
        Returns
        `str`: Reply to user
        """
        if not schedule:
            log.info(f'[instruction][{user_id}]claimDailyReward: honkai={honkai}')
        check, msg = self.checkUserData(user_id, update_use_time=(not schedule))
        if check == False:
            return msg
        client = self.__getGenshinClient(user_id)
        
        game_name = {genshin.Game.GENSHIN: 'Genshin Impact', genshin.Game.HONKAI: 'Honkai Impact 3'}
        async def claimReward(game: genshin.Game, retry: int = 5) -> str:
            try:
                reward = await client.claim_daily_reward(game=game)
            except genshin.errors.AlreadyClaimed:
                return f'{game_name[game]}Today\'s reward has been claimed！'
            except genshin.errors.GenshinException as e:
                log.info(f'[exception][{user_id}]claimDailyReward: {game_name[game]}[retcode]{e.retcode} [exceptions]{e.original}')
                if e.retcode == 0 and retry > 0:
                    await asyncio.sleep(0.5)
                    return await claimReward(game, retry - 1)
                if e.retcode == -10002 and game == genshin.Game.HONKAI:
                    return 'Honkai Impact 3 failed to sign in, the character information was not queried, please confirm whether the captain has bound the new HoYoverse pass'
                return f'{game_name[game]}Failed to sign in：[retcode]{e.retcode} [content]{e.original}'
            except Exception as e:
                log.error(f'[exception][{user_id}]claimDailyReward: {game_name[game]}[exceptions]{e}')
                return f'{game_name[game]}Failed to sign in：{e}'
            else:
                return f'{game_name[game]}Sign in today successfully, got {reward.amount}x {reward.name}！'

        result = await claimReward(genshin.Game.GENSHIN)
        if honkai:
            result = result + ' ' + await claimReward(genshin.Game.HONKAI)
        
        # Hoyolab community sign-in
        try:
            await client.check_in_community()
        except genshin.errors.GenshinException as e:
            log.info(f'[exception][{user_id}]claimDailyReward: Hoyolab[retcode]{e.retcode} [exceptions]{e.original}')
        except Exception as e:
            log.error(f'[exception][{user_id}]claimDailyReward: Hoyolab[exceptions]{e}')
        
        return result

    async def getSpiralAbyss(self, user_id: str, previous: bool = False) -> Union[str, genshin.models.SpiralAbyss]:
        """Get Spiral Abyss Information

        ------
        Parameters
        user_id `str`: User Discord ID
        previous `bool`: `True` to query the information of the previous issue, `False` to query the information of this issue
        ------
        Returns
        `Union[str, SpiralAbyss]`: When an exception occurs, the error message `str` is returned, and the query result `SpiralAbyss` is returned under normal conditions.
        """
        log.info(f'[instruction][{user_id}]getSpiralAbyss: previous={previous}')
        check, msg = self.checkUserData(user_id)
        if check == False:
            return msg
        client = self.__getGenshinClient(user_id)
        try:
            # In order to refresh the battle data list, you need to make a request to the record card first
            await client.get_record_cards()
            abyss = await client.get_genshin_spiral_abyss(int(self.__user_data[user_id]['uid']), previous=previous)
        except genshin.errors.GenshinException as e:
            log.error(f'[exception][{user_id}]getSpiralAbyss: [retcode]{e.retcode} [exceptions]{e.original}')
            return e.original
        except Exception as e:
            log.error(f'[exception][{user_id}]getSpiralAbyss: [exceptions]{e}')
            return f'{e}'
        else:
            return abyss
    
    async def getTravelerDiary(self, user_id: str, month: int) -> Union[str, discord.Embed]:
        """Get user's Travelers Notes

        ------
        Parameters:
        user_id `str`: User Discord ID
        month `int`: Month to query
        ------
        Returns:
        `Union[str, discord.Embed]`: When an exception occurs, the error message `str` is returned, and the query result `discord.Embed` is returned under normal conditions.
        """
        log.info(f'[instruction][{user_id}]getTravelerDiary: month={month}')
        check, msg = self.checkUserData(user_id)
        if check == False:
            return msg
        client = self.__getGenshinClient(user_id)
        try:
            diary = await client.get_diary(int(self.__user_data[user_id]['uid']), month=month)
        except genshin.errors.GenshinException as e:
            log.error(f'[exception][{user_id}]getTravelerDiary: [retcode]{e.retcode} [exceptions]{e.original}')
            result = e.original
        except Exception as e:
            log.error(f'[exception][{user_id}]getTravelerDiary: [exceptions]{e}')
            result = f'{e}'
        else:    
            d = diary.data
            result = discord.Embed(
                title=f'{diary.nickname}Traveler\'s Notes：{month} month',
                description=f'Primogems income compared to last{"add" if d.primogems_rate > 0 else "subtract"}{abs(d.primogems_rate)}%，Mora income compared to last month{"add" if d.mora_rate > 0 else "subtract"} {abs(d.mora_rate)}%',
                color=0xfd96f4
            )
            result.add_field(
                name='Obtained this month', 
                value=f'Primogems：{d.current_primogems} ({round(d.current_primogems/160)})　Last Month：{d.last_primogems} ({round(d.last_primogems/160)})\n'
                    f'Mora：{format(d.current_mora, ",")}　Last Month：{format(d.last_mora, ",")}',
                inline=False
            )
            # Divide the note composition into two field
            for i in range(0, 2):
                msg = ''
                length = len(d.categories)
                for j in range(round(length/2*i), round(length/2*(i+1))):
                    msg += f'{d.categories[j].name[0:2]}：{d.categories[j].percentage}%\n'
                result.add_field(name=f'Primogems Income Composition ({i+1})', value=msg, inline=True)
        finally:
            return result
    
    async def getRecordCard(self, user_id: str) -> Union[str, Tuple[genshin.models.RecordCard, genshin.models.PartialGenshinUserStats]]:
        """Get user record card

        ------
        Parameters:
        user_id `str`: User Discord ID
        ------
        Returns:
        `str | (RecordCard, PartialGenshinUserStats)`: When an exception occurs, the error message `str` is returned, and the query `(RecordCard, PartialGenshinUserStats)` result is returned under normal conditions. 
        """
        log.info(f'[instruction][{user_id}]getRecordCard')
        check, msg = self.checkUserData(user_id)
        if check == False:
            return msg
        client = self.__getGenshinClient(user_id)
        try:
            cards = await client.get_record_cards()
            userstats = await client.get_partial_genshin_user(int(self.__user_data[user_id]['uid']))
        except genshin.errors.GenshinException as e:
            log.error(f'[exception][{user_id}]getRecordCard: [retcode]{e.retcode} [exceptions]{e.original}')
            return e.original
        except Exception as e:
            log.error(f'[execption][{user_id}]getRecordCard: [exceptions]{e}')
            return str(e)
        else:
            for card in cards:
                if card.uid == int(self.__user_data[user_id]['uid']):
                    return (card, userstats)
            return 'Can\'t find Genshin record card'

    async def getCharacters(self, user_id: str) -> Union[str, Sequence[genshin.models.Character]]:
        """Get all user account data

        ------
        Parameters:
        user_id `str`: User Discord ID
        ------
        Returns:
        `str | Sequence[Character]`: When an exception occurs, the error message `str` is returned, and the query result `Sequence[Character]` is returned under normal conditions.
        """
        log.info(f'[instruction][{user_id}]getCharacters')
        check, msg = self.checkUserData(user_id)
        if check == False:
            return msg
        client = self.__getGenshinClient(user_id)
        try:
            characters = await client.get_genshin_characters(int(self.__user_data[user_id]['uid']))
        except genshin.errors.GenshinException as e:
            log.error(f'[exception][{user_id}]getCharacters: [retcode]{e.retcode} [exceptions]{e.original}')
            return e.original
        except Exception as e:
            log.error(f'[exception][{user_id}]getCharacters: [exceptions]{e}')
            return str(e)
        else:
            return characters
    
    def checkUserData(self, user_id: str, *, checkUID = True, update_use_time = True) -> Tuple[bool, str]:
        """Check if user-related data has been saved in the database
        
        ------
        Parameters
        user_id `str`: User Discord ID
        checkUID `bool`: Whether to check UID
        update_use_time `bool`: Whether to update the user's last usage time
        ------
        Returns
        `bool`: `True` check is successful, the data exists in the database; `False` check fails, the data does not exist in the database
        `str`: Reply to the user when the check fails.
        """
        if user_id not in self.__user_data.keys():
            log.info(f'[info][{user_id}]checkUserData: User not found')
            return False, f'User not found，Please set a Cookie first(Enter `/cookie` to display instructions)'
        else:
            if 'cookie' not in self.__user_data[user_id].keys():
                log.info(f'[info][{user_id}]checkUserData: Cookie not found')
                return False, f'Cookie not found，Please set cookies first (Enter `/cookie` to display instructions)'
            if checkUID and 'uid' not in self.__user_data[user_id].keys():
                log.info(f'[info][{user_id}]checkUserData: Account UID not found')
                return False, f'Account UID not found，Please set UID first (Use `/uid` to set UID)'
        if update_use_time:
            user_last_use_time.update(user_id)
        return True, None
    
    def clearUserData(self, user_id: str) -> str:
        """Permanently delete user data from the database

        ------
        Parameters
        user_id `str`: User Discord ID
        ------
        Returns:
        `str`: Reply to user
        """
        log.info(f'[instruction][{user_id}]clearUserData')
        try:
            del self.__user_data[user_id]
            user_last_use_time.deleteUser(user_id)
        except:
            return 'Failed to delete，User data not found'
        else:
            self.__saveUserData()
            return 'User data has been deleted'
    
    def deleteExpiredUserData(self) -> None:
        """Delete users that have not been used for more than 120 days"""
        now = datetime.now()
        count = 0
        user_data = dict(self.__user_data)
        for user_id in user_data.keys():
            if user_last_use_time.checkExpiry(user_id, now, 120) == True:
                self.clearUserData(user_id)
                count += 1
        log.info(f'[info][System]deleteExpiredUserData: {len(user_data)} Users checked，Deleted {count} Expired users')

    def parseAbyssOverview(self, abyss: genshin.models.SpiralAbyss) -> discord.Embed:
        """Analyze the abyss overview data including Date, Progress, Number of Tries, Stars obtained...etc.

        ------
        Parameters
        abyss `SpiralAbyss`: Spiral Abyss Information
        ------
        Returns
        `discord.Embed`: discord embed format
        """
        result = discord.Embed(description=f'Phase {abyss.season} ：{abyss.start_time.astimezone().strftime("%d.%m.%Y")} ~ {abyss.end_time.astimezone().strftime("%d.%m.%Y")}', color=0x6959c1)
        get_char = lambda c: ' ' if len(c) == 0 else f'{getCharacterName(c[0])}：{c[0].value}'
        result.add_field(
            name=f'Deepest Descent：{abyss.max_floor}　Number of Tries：{abyss.total_battles}　★：{abyss.total_stars}',
            value=  f'{"👑 Congratulations on 36 stars!" if abyss.total_stars == 36 else "You will get there don't worry :D"}'
                    f'[Most Kills] {get_char(abyss.ranks.most_kills)}\n'
                    f'[Strongest Strike] {get_char(abyss.ranks.strongest_strike)}\n'
                    f'[Most Damage Taken] {get_char(abyss.ranks.most_damage_taken)}\n'
                    f'[Most Burst Used(Q)] {get_char(abyss.ranks.most_bursts_used)}\n'
                    f'[Most Skills Used(E)] {get_char(abyss.ranks.most_skills_used)}',
            inline=False
        )
        return result
    
    def parseAbyssFloor(self, embed: discord.Embed, abyss: genshin.models.SpiralAbyss, full_data: bool = False) -> discord.Embed:
        """Analyze each floor of the abyss, add the number of stars on each floor and the character data used to the embed
        
        ------
        Parameters
        embed `discord.Embed`: Embedded data obtained from the `parseAbyssOverview` function
        abyss `SpiralAbyss`: Spiral Abysss Information
        full_data `bool`: `True` means parsing all floors; `False` means parsing only the last level.
        ------
        Returns
        `discord.Embed`: discord embed format
        """
        for floor in abyss.floors:
            if full_data == False and floor is not abyss.floors[-1]:
                continue
            for chamber in floor.chambers:
                name = f'{floor.floor}-{chamber.chamber}　★{chamber.stars}'
                # Obtain the character name of the upper and lower half of the abyss
                chara_list = [[], []]
                for i, battle in enumerate(chamber.battles):
                    for chara in battle.characters:
                        chara_list[i].append(getCharacterName(chara))
                value = f'[{".".join(chara_list[0])}]／\n[{".".join(chara_list[1])}]'
                embed.add_field(name=name, value=value)
        return embed
    
    def parseCharacter(self, character: genshin.models.Character) -> discord.Embed:
        """Analyze characters, including constellation, level, talent, weapons, artifacts
        
        ------
        Parameters
        character `Character`: Character Information
        ------
        Returns
        `discord.Embed`: discord embed format
        """
        color = {'pyro': 0xfb4120, 'electro': 0xbf73e7, 'hydro': 0x15b1ff, 'cryo': 0x70daf1, 'dendro': 0xa0ca22, 'anemo': 0x5cd4ac, 'geo': 0xfab632}
        embed = discord.Embed(color=color.get(character.element.lower()))
        embed.set_thumbnail(url=character.icon)
        embed.add_field(name=f'{character.rarity}★ {character.name}', inline=True, value=f'Constellation：{character.constellation}\nLevel: {character.level}\n好感：Lv. {character.friendship}')

        weapon = character.weapon
        embed.add_field(name=f'{weapon.rarity}★ {weapon.name}', inline=True, value=f'Refinement Rank：{weapon.refinement}\nLevel：{weapon.level}')

        if character.constellation > 0:
            number = {1: '1', 2: '2', 3: '3', 4: '4', 5: '5', 6: '6'}
            msg = '\n'.join([f'{C number[constella.pos]} ：{constella.name}' for constella in character.constellations if constella.activated])
            embed.add_field(name='Constellation', inline=False, value=msg)

        if len(character.artifacts) > 0:
            msg = '\n'.join([f'{artifact.pos_name}：{artifact.set.name}' for artifact in character.artifacts])
            embed.add_field(name='Artifact', inline=False, value=msg)

        return embed

    def __parseNotes(self, notes: genshin.models.Notes, shortForm: bool = False) -> str:
        result = ''
        # Resin
        result += f'Current Resin：{notes.current_resin}/{notes.max_resin}\n'
        if notes.current_resin >= notes.max_resin:
            recover_time = 'FULL！'
        else:
            day_msg = getDayOfWeek(notes.resin_recovery_time)
            recover_time = f'{day_msg} {notes.resin_recovery_time.strftime("%H:%M")}'
        result += f'Full Recovery Time：{recover_time}\n'
        # Daily,Weekly
        if not shortForm:
            result += f'Daily Commissions: {notes.max_commissions - notes.completed_commissions} Left\n'
            result += f'Weekly Boss Discount: {notes.remaining_resin_discounts} Left\n'
        result += f'--------------------\n'
        # Realm Currency
        result += f'Realm Currency：{notes.current_realm_currency}/{notes.max_realm_currency}\n'
        if notes.max_realm_currency > 0:
            if notes.current_realm_currency >= notes.max_realm_currency:
                recover_time = 'FULL！'
            else:
                day_msg = getDayOfWeek(notes.realm_currency_recovery_time)
                recover_time = f'{day_msg} {notes.realm_currency_recovery_time.strftime("%H:%M")}'
            result += f'Full Recovery Time：{recover_time}\n'
        # Parameteric Transformer
        if notes.transformer_recovery_time != None:
            t = notes.remaining_transformer_recovery_time
            if t.days > 0:
                recover_time = f' {t.days} days left'
            elif t.hours > 0:
                recover_time = f' {t.hours} hours left'
            elif t.minutes > 0:
                recover_time = f' {t.minutes} minutes left'
            elif t.seconds > 0:
                recover_time = f' {t.seconds} seconds left'
            else:
                recover_time = 'Not in Cooldown'
            result += f'Parametric Transformer　：{recover_time}\n'
        # Expedition Dispatch Remailing
        if not shortForm:
            result += f'--------------------\n'
            exped_finished = 0
            exped_msg = ''
            for expedition in notes.expeditions:
                exped_msg += f'· {getCharacterName(expedition.character)}'
                if expedition.finished:
                    exped_finished += 1
                    exped_msg += '：Completed\n'
                else:
                    day_msg = getDayOfWeek(expedition.completion_time)
                    exped_msg += f' Completion Time：{day_msg} {expedition.completion_time.strftime("%H:%M")}\n'
            result += f'Expeditions Completed ：{exped_finished}/{len(notes.expeditions)}\n'
            result += exped_msg
        
        return result
        
    def __saveUserData(self) -> None:
        try:
            with open('data/user_data.json', 'w', encoding='utf-8') as f:
                json.dump(self.__user_data, f)
        except:
            log.error('[exception][System]GenshinApp > __saveUserData: Archive Failed')

    def __getGenshinClient(self, user_id: str) -> genshin.Client:
        uid = self.__user_data[user_id].get('uid')
        client = genshin.Client(region=genshin.Region.OVESEAS, lang='en-us')
        client.set_cookies(self.__user_data[user_id]['cookie'])
        client.default_game = genshin.Game.GENSHIN
        return client

genshin_app = GenshinApp()
