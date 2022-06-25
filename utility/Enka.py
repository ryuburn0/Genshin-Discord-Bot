import aiohttp
import discord
from typing import Any, Dict, List, Union, Optional
from utility.emoji import emoji
from utility.config import config
from data.game.characters import characters_map
from data.game.weapons import weapons_map
from data.game.artifacts import artifcats_map
from data.game.namecards import namecards_map
from data.game.fight_prop import fight_prop_map, get_prop_name

class Showcase:
    data: Dict[str, Any] = None
    uid: int = 0
    url: str = ''

    def __init__(self) -> None:
        pass

    async def getEnkaData(self, uid: int) -> None:
        """Get the character showcase data of the specified player UID using the API"""
        self.uid = uid
        self.url = f'https://enka.shinshin.moe/u/{uid}'
        api_url = self.url + '/__data.json' + (f"?key={config.enka_api_key}" if config.enka_api_key else '')
        async with aiohttp.request('GET', api_url) as resp:
            if resp.status == 200:
                self.data = await resp.json()
            else:
                raise Exception(f"[{resp.status} {resp.reason}]An error occurred with the API server or the player profile does not exist")

    def getPlayerOverviewEmbed(self) -> discord.Embed:
        """Embed message to get player's basic data"""
        player: Dict[str, Any] = self.data['playerInfo']
        embed = discord.Embed(
            title=player.get('nickname', str(self.uid)),
            description=
                f"「{player.get('signature', '')}」\n"
                f"Adventure Rank：{player.get('level', 1)}\n"
                f"World Level：{player.get('worldLevel', 0)}\n"
                f"Achievements Completed：{player.get('finishAchievementNum', 0)}\n"
                f"Spiral Abyss：{player.get('towerFloorIndex', 0)}-{player.get('towerLevelIndex', 0)}"
        )
        if avatarId := player.get('profilePicture', { }).get('avatarId'):
            avatar_url = characters_map.get(str(avatarId), { }).get('icon')
            embed.set_thumbnail(url=avatar_url)
        if namecard := namecards_map.get(player.get('nameCardId', 0), { }).get('Card'):
            card_url = f'https://enka.shinshin.moe/ui/{namecard}.png'
            embed.set_image(url=card_url)
        embed.set_footer(text=f'UID: {self.uid}')
        return embed

    def getCharacterStatEmbed(self, index: int) -> discord.Embed:
        """Get embed message for character panel"""
        id = str(self.data['playerInfo']['showAvatarInfoList'][index]['avatarId'])
        embed = self.__getDefaultEmbed(id)
        embed.title += '\'s character showcase'
        if 'avatarInfoList' not in self.data:
            embed.description = 'In-game character details are set to be private'
            return embed
        avatarInfo: Dict[str, Any] = self.data['avatarInfoList'][index]
        # Talent Level[A, E, Q]
        skill_level = [0, 0, 0]
        for i in range(3):
            if 'skillOrder' in characters_map[id]:
                skillId = characters_map[id]['skillOrder'][i]
            else:
                skillId = list(avatarInfo['skillLevelMap'])[i]
            skill_level[i] = avatarInfo['skillLevelMap'][str(skillId)]
        # Character Information
        embed.add_field(
            name=f"Character Profile",
            value=f"Constellation：{0 if 'talentIdList' not in avatarInfo else len(avatarInfo['talentIdList'])}\n"
                  f"Level: {avatarInfo['propMap']['4001']['val']}\n"
                  f"Talent：{skill_level[0]}/{skill_level[1]}/{skill_level[2]}\n"
                  f"Friendship Lv.: {avatarInfo['fetterInfo']['expLevel']}",
        )
        # Wepon Information
        equipList: List[Dict[str, Any]] = avatarInfo['equipList']
        if 'weapon' in equipList[-1]:
            weapon = equipList[-1]
            weaponStats = weapon['flat']['weaponStats']
            refinement = 1
            if 'affixMap' in weapon['weapon']:
                refinement += list(weapon['weapon']['affixMap'].values())[0]
            embed.add_field(
                name=f"{weapon['flat']['rankLevel']}★ {weapons_map[weapon['itemId']]['name']}",
                value=f"Refinement：{refinement} \n"
                      f"Level: {weapon['weapon']['level']}\n"
                      f"Base Atk:{weaponStats[0]['statValue']}\n"
                      f"{(weaponStats[1]['appendPropId']: weaponStats[1]['statValue']) if len(weaponStats) > 1 else ''}"
            )
        # Stats
        prop: Dict[str, float] = avatarInfo['fightPropMap']
        substat: str = '\n'.join([self.__getCharacterFightPropSentence(int(id), prop[id]) for
            id in ['20', '22', '28', '26', '23', '30', '40', '41', '42', '43', '44', '45', '46'] if prop[id] > 0])
        embed.add_field(
            name='Stats',
            value=f"HP：{round(prop['2000'])} ({round(prop['1'])} +{round(prop['2000'])-round(prop['1'])})\n"
                  f"ATK：{round(prop['2001'])} ({round(prop['4'])} +{round(prop['2001'])-round(prop['4'])})\n"
                  f"DEF：{round(prop['2002'])} ({round(prop['7'])} +{round(prop['2002'])-round(prop['7'])})\n"
                  f"{substat}",
            inline=False
        )
        return embed
    
    def getArtifactStatEmbed(self, index: int) -> discord.Embed:
        """Get the embedded message of the character's artifacts"""
        id = str(self.data['playerInfo']['showAvatarInfoList'][index]['avatarId'])
        embed = self.__getDefaultEmbed(id)
        embed.title += ' Artifact'

        if 'avatarInfoList' not in self.data:
            embed.description = 'In-game character details are set to private'
            return embed
        avatarInfo: Dict[str, Any] = self.data['avatarInfoList'][index]
        
        pos_name_map = {1: 'Flower', 2: 'Feather', 3: 'Sands', 4: 'Goblet', 5: 'Circlet'}
        substat_sum: Dict[str, float] = dict() # Total Substat

        equip: Dict[str, Any]
        for equip in avatarInfo['equipList']:
            if 'reliquary' not in equip:
                continue
            artifact_id: int = equip['itemId'] // 10
            flat = equip['flat']
            pos_name = pos_name_map[artifcats_map[artifact_id]['pos']]
            # Main Stat
            embed_value = f"__**{self.__getStatPropSentence(flat['reliquaryMainstat']['mainPropId'], flat['reliquaryMainstat']['statValue'])}**__\n"
            # Sub Stat
            for substat in flat['reliquarySubstats']:
                prop: str = substat['appendPropId']
                value: Union[int, float] = substat['statValue']
                embed_value += f"{self.__getStatPropSentence(prop, value)}\n"
                substat_sum[prop] = substat_sum.get(prop, 0) + value
            
            embed.add_field(name=f"pos_name + '：'{artifcats_map[artifact_id]['name']}", value=embed_value)

    def __getDefaultEmbed(self, character_id: str) -> discord.Embed:
        id = character_id
        color = {'pyro': 0xfb4120, 'electro': 0xbf73e7, 'hydro': 0x15b1ff, 'cryo': 0x70daf1, 'dendro': 0xa0ca22, 'anemo': 0x5cd4ac, 'geo': 0xfab632}
        embed = discord.Embed(
            title=f"{characters_map[id]['rarity']}★ {characters_map[id]['name']}",
            color=color.get(characters_map[id]['element'].lower())
        )
        embed.set_thumbnail(url=characters_map[id]['icon'])
        embed.set_author(name=f"{self.data['playerInfo']['nickname']} Character Showcase", url=self.url)
        embed.set_footer(text=f"{self.data['playerInfo']['nickname']}．Lv. {self.data['playerInfo']['level']}．UID: {self.uid}")

        return embed

    def __getCharacterFightPropSentence(self, prop: int, value: Union[int, float]) -> str:
        emoji_str = ''
        prop_name = get_prop_name(prop)
        if '%' in prop_name:
            return emoji_str + prop_name.replace('%', f'：{round(value * 100, 1)}%')
        return emoji_str + prop_name + f'：{round(value)}'

    def __getStatPropSentence(self, prop: str, value: Union[int, float]) -> str:
        emoji_str = ''
        prop_name = get_prop_name(prop)
        if '%' in prop_name:
            return emoji_str + prop_name.replace('%', f'+{value}%')
        return emoji_str + prop_name + f'+{value}'

class ShowcaseCharactersDropdown(discord.ui.Select):
    """Showcase Characters Dropdown"""
    showcase: Showcase
    def __init__(self, showcase: Showcase) -> None:
        self.showcase = showcase
        avatarInfoList: List[Dict[str, Any]] = showcase.data['playerInfo']['showAvatarInfoList']
        options = []
        for i, avatarInfo in enumerate(avatarInfoList):
            id = str(avatarInfo['avatarId'])
            level: str = avatarInfo['level']
            rarity: int = characters_map[id]['rarity']
            element: str = characters_map[id]['element']
            name: str = characters_map[id]['name']
            options.append(discord.SelectOption(
                label=f'{rarity}★ Lv.{level} {name}',
                value=str(i),
                emoji=emoji.elements.get(element.lower())
            ))
        super().__init__(placeholder=f'Choose a character to showcase：', options=options)
    
    async def callback(self, interaction: discord.Interaction) -> None:
        character_index = int(self.values[0])
        embed = self.showcase.getCharacterStatEmbed(character_index)
        view = ShowcaseView(self.showcase, character_index)
        await interaction.response.edit_message(embed=embed, view=view)

class CharacterStatButton(discord.ui.Button):
    """Character stat buttons"""
    showcase: Showcase
    character_index: int
    def __init__(self, showcase: Showcase, character_index: int):
        super().__init__(style=discord.ButtonStyle.green, label='Character Panel')
        self.showcase = showcase
        self.character_index = character_index
    
    async def callback(self, interaction: discord.Interaction) -> Any:
        embed = self.showcase.getCharacterStatEmbed(self.character_index)
        await interaction.response.edit_message(embed=embed)

class CharacterArtifactButton(discord.ui.Button):
    """Character artifact button"""
    showcase: Showcase
    character_index: int
    def __init__(self, showcase: Showcase, character_index: int):
        super().__init__(style=discord.ButtonStyle.primary, label='Artifact Panel')
        self.showcase = showcase
        self.character_index = character_index
    
    async def callback(self, interaction: discord.Interaction) -> Any:
        embed = self.showcase.getArtifactStatEmbed(self.character_index)
        await interaction.response.edit_message(embed=embed)

class ShowcaseView(discord.ui.View):
    """Character showcase view，Character stat button、Artifact button，Character dropdown"""
    def __init__(self, showcase: Showcase, character_index: Optional[int] = None):
        super().__init__(timeout=config.discord_view_long_timeout)
        if character_index != None:
            self.add_item(CharacterStatButton(showcase, character_index))
            self.add_item(CharacterArtifactButton(showcase ,character_index))
        if 'showAvatarInfoList' in showcase.data['playerInfo']:
            self.add_item(ShowcaseCharactersDropdown(showcase))
