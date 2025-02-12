import random
import asyncio
import json
from openai import OpenAI
import speech_recognition as sr
import pyttsx3
import os

# 配置
API_KEY = "sk-e420e460d1904ea3871965618c61ff1b"
BASE_URL = "https://api.deepseek.com"
isKill = False

# 角色设定
ROLES = {
    "狼人": {"阵营": "狼人阵营", "夜晚行动": "选择一名玩家进行袭击",
             "胜利条件": "消灭所有村民和神职角色，千萬不能暴露自己的身份"},
    "预言家": {"阵营": "村民阵营", "夜晚行动": "选择一名玩家查看身份",
               "胜利条件": "所有狼人被消灭，你可以選擇隱瞞身份或者說出你掌握的信息"},
    "女巫": {"阵营": "村民阵营", "夜晚行动": "有一瓶解药和一瓶毒药，决定是否使用",
             "胜利条件": "所有狼人被消灭，你可以選擇隱瞞身份或者說出你掌握的信息"},
    "猎人": {"阵营": "村民阵营", "夜晚行动": "如果被狼人袭击，可以选择带走一名玩家",
             "胜利条件": "所有狼人被消灭，你可以選擇隱瞞身份或者說出你掌握的信息"},
    "平民": {"阵营": "村民阵营", "夜晚行动": "无行动", "胜利条件": "所有狼人被消灭，你可以選擇捏造身份替隊友擋刀"}
}

# 初始化语音识别和语音合成
recognizer = sr.Recognizer()
engine = pyttsx3.init()


def get_voice_input():
    """通过麦克风获取语音输入并转换为文字"""
    try:
        with sr.Microphone() as source:
            print("请开始说话...")
            recognizer.adjust_for_ambient_noise(source)
            audio = recognizer.listen(source)
            transcribed_text = recognizer.recognize_google(audio, language="zh-CN")
            print(f"语音识别结果: {transcribed_text}")
            return transcribed_text
    except sr.UnknownValueError:
        print("无法识别语音")
    except sr.RequestError as e:
        print(f"语音识别错误: {e}")
    except Exception as e:
        print(f"语音输入错误: {e}")
    return input("请直接输入文字: ")  # 作为备选方案


def synthesize_and_play(text):
    """将文本合成语音并播放"""
    try:
        engine.say(text)
        engine.runAndWait()
        print(f"语音合成并播放完成: {text}")
    except Exception as e:
        print(f"语音合成错误: {e}")


class Player:
    def __init__(self, player_id, name, role):
        self.id = player_id
        self.name = name
        self.role = role
        self.alive = True
        self.checked = False  # 是否被预言家查验过
        self.conversation_history = []
        self.saved = False  # 是否被女巫救过
        self.active = []

    def __repr__(self):
        return f"{self.name} ({self.role})"

    def vote(self, players):
        if not self.alive:
            return None

        if self.name == "人类玩家":
            return None  # 玩家的投票逻辑保持不变

        # 使用 AI 分析投票
        client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

        # 构建投票分析的上下文
        alive_players = [p for p in players if p.alive and p != self]
        player_info = []
        for p in alive_players:
            active_records = "无" if not p.active else ", ".join(p.active)
            conversation_records = "无" if not p.conversation_history else ", ".join(p.conversation_history)
            # player_info.append(f"- {p.name} 的行为记录：{active_records}")
            player_info.append(f"- {p.name} 的发言记录：{conversation_records}")

        context = "\n".join(player_info)

        prompt = f"""你是狼人杀游戏中的 {self.name}，身份是 {self.role}。
        ## 当前情况：
        - 你的行动记录：{', '.join(self.active)}
        - 存活玩家：{', '.join(p.name for p in alive_players)}
        
        ## 玩家行为和发言分析：
        {context}
        
        ## 你的任务：
        1. 分析每个玩家的可疑程度
        2. 根据你的身份特点（{self.role}）选择投票目标
        3. 只需要返回投票玩家的名字，不要其他内容
        """

        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是一个狼人杀专家，擅长分析玩家行为。请只返回一个玩家名字。"},
                    {"role": "user", "content": prompt}
                ]
            )

            vote_target = response.choices[0].message.content.strip()
            # 找到对应的玩家对象
            for player in alive_players:
                if player.name in vote_target:
                    return player

        except Exception as e:
            print(f"AI投票分析出错: {e}")

        # 如果AI分析失败，随机投票作为后备方案
        return random.choice(alive_players)

    def perform_night_action(self, players, killed_player=None):
        if not self.alive:
            return None

        if self.role == "狼人":
            global isKill
            if not isKill:
                if self.name == "人类玩家":
                    # 显示可选择的目标
                    print("\n你是狼人，请选择要袭击的玩家：")
                    valid_targets = [p for p in players if p.alive and p.role != "狼人"]
                    for i, target in enumerate(valid_targets):
                        print(f"{i + 1}. {target.name}")

                    while True:
                        try:
                            choice = input("请输入目标编号: ")
                            target_idx = int(choice) - 1
                            if 0 <= target_idx < len(valid_targets):
                                target = valid_targets[target_idx]
                                break
                            else:
                                print("无效的选择，请重新输入")
                        except ValueError:
                            print("请输入有效的数字")
                else:
                    # AI狼人的选择保持不变
                    target = random.choice([p for p in players if p.alive and p.role != "狼人"])

                isKill = True
                self.active.append(f"我自己 {self.name} 是狼人殺了 {target.name}")
                return target

        elif self.role == "预言家":
            if self.name == "人类玩家":
                # 显示可选择的目标
                print("\n你是预言家，请选择要查验的玩家：")
                valid_targets = [p for p in players if p.alive and p != self and not p.checked]
                if valid_targets:
                    for i, target in enumerate(valid_targets):
                        print(f"{i + 1}. {target.name}")

                    while True:
                        try:
                            choice = input("请输入目标编号: ")
                            target_idx = int(choice) - 1
                            if 0 <= target_idx < len(valid_targets):
                                target = valid_targets[target_idx]
                                target.checked = True
                                print(f"\n查验结果：{target.name} 的身份是 {target.role}")
                                self.active.append(
                                    f"我自己 {self.name} 是预言家查验了 {target.name}，身份是 {target.role}")
                                break
                            else:
                                print("无效的选择，请重新输入")
                        except ValueError:
                            print("请输入有效的数字")
                else:
                    print("没有可以查验的目标")
            else:
                # AI预言家的行为保持不变
                unchecked_players = [p for p in players if p.alive and p != self and not p.checked]
                if unchecked_players:
                    target = random.choice(unchecked_players)
                    target.checked = True
                    self.active.append(f"我自己 {self.name} 是预言家查验了 {target.name}，身份是 {target.role}")

        elif self.role == "女巫" and killed_player:
            if self.name == "人类玩家":
                if killed_player.alive:  # 被狼人袭击的玩家
                    print(f"\n今晚 {killed_player.name} 被狼人袭击了")
                    if not killed_player.saved:  # 还没被救过
                        while True:
                            choice = input("是否使用解药救他？(y/n): ").lower()
                            if choice in ['y', 'n']:
                                if choice == 'y':
                                    killed_player.saved = True
                                    killed_player.alive = True
                                    self.active.append(f"我自己 {self.name} 是女巫使用解药救活了 {killed_player.name}")
                                break
                            killed_player.alive = False
                            print("请输入 y 或 n")
                    else:
                        print("该玩家已经被救过一次，无法再次使用解药")
            else:
                # AI女巫的行为保持不变
                if not killed_player.saved and random.random() < 0.7:  # 70%概率使用解药
                    killed_player.saved = True
                    killed_player.alive = True
                    self.active.append(f"我自己 {self.name} 是女巫使用解药救活了 {killed_player.name}")
                else:
                    killed_player.alive = False
        return None


class WerewolfGame:
    def __init__(self):
        self.players = [Player(i, "人类玩家" if i == 0 else f"ai玩家{i}", None) for i in range(6)]
        role_distribution = ["狼人", "平民", "预言家", "女巫", "平民", "狼人"]
        random.shuffle(role_distribution)
        for i, role in enumerate(role_distribution):
            self.players[i].role = role
        self.alive_players = set(self.players)

    def night_phase(self):
        print("\n--- 天黑请闭眼 ---")
        global isKill
        isKill = False
        killed_player = None

        # 狼人行动
        print("\n--- 狼人请睜眼 ---")
        for player in self.alive_players:
            if player.role == "狼人":
                target = player.perform_night_action(self.players)
                if target:
                    print(f"狼人 {player.name} 袭击了 {target.name}")
                    # target.alive = False
                    killed_player = target

        # 女巫行动
        print("\n--- 狼人请閉眼，女巫請睜眼 ---")
        for player in self.alive_players:
            if player.role == "女巫":
                player.perform_night_action(self.players, killed_player)

        # 预言家行动
        print("\n--- 女巫请閉眼，預言家請睜眼 ---")
        for player in self.alive_players:
            if player.role == "预言家":
                player.perform_night_action(self.players)

        self.alive_players = {p for p in self.players if p.alive}

    def day_phase(self):
        print("\n--- 天亮了 ---")
        self.alive_players = {p for p in self.players if p.alive}
        context = f"存活玩家：{', '.join(p.name for p in self.alive_players)}"
        for player in self.alive_players:
            if player.alive:
                if player.name != "人类玩家":
                    ai_response = ai_speak(player, context, player.conversation_history)
                    print(f"{player.name}: {ai_response}")
                    player.conversation_history.append(f"{player.name}: {ai_response}")
                    synthesize_and_play(ai_response)  # AI 发言合成语音
                else:
                    print("轮到你发言了，请说话...")
                    player_speech = get_voice_input()
                    player.conversation_history.append(f"人类玩家: {player_speech}")
                    synthesize_and_play(player_speech)  # 用户发言合成语音

    def voting_phase(self):
        print("\n--- 投票环节 ---")
        votes = {p: 0 for p in self.alive_players}
        for player in self.alive_players:
            if player.name == "人类玩家":
                print("请说出你要投票的玩家名字...")
                while True:
                    vote_input = get_voice_input()
                    target = None
                    for p in self.alive_players:
                        if p.name in vote_input:
                            target = p
                            break
                    if target:
                        votes[target] += 1
                        print(f"你投票给了 {target.name}")
                        break
                    else:
                        print("未找到该玩家，请重新说出玩家名字")
            else:
                vote = player.vote(self.alive_players)
                if vote:
                    votes[vote] += 1
                    print(f"{player.name} 投票给了 {vote.name}")

        max_votes = max(votes.values())
        tied_players = [p for p, v in votes.items() if v == max_votes]

        if len(tied_players) > 1:
            print("\n出现平票！随机选择一名玩家出局...")
            eliminated = random.choice(tied_players)
        else:
            eliminated = max(votes, key=votes.get)

        print(f"\n{eliminated.name} 被投票出局，身份是 {eliminated.role}！")
        self.alive_players.remove(eliminated)
        eliminated.alive = False

    def check_winner(self):
        wolf_count = sum(1 for p in self.alive_players if p.role == "狼人")
        if wolf_count == 0:
            print("\n🎉 村民阵营胜利！")
            return True
        if wolf_count >= len(self.alive_players) / 2:
            print("\n🐺 狼人阵营胜利！")
            return True
        return False

    def start(self):
        human_player = [p for p in self.players if p.name == "人类玩家"][0]
        print("\n游戏开始！你的身份是:", human_player.role)
        
        # 如果人类玩家是狼人，显示其他狼人身份
        if human_player.role == "狼人":
            wolf_teammates = [p for p in self.players if p.role == "狼人" and p.name != "人类玩家"]
            print("你的狼人队友是:", ", ".join(p.name for p in wolf_teammates))
        
        while len(self.alive_players) > 2:
            self.night_phase()
            self.day_phase()
            self.voting_phase()
            if self.check_winner():
                break


def ai_speak(player, context, conversation_history):
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    role_info = ROLES[player.role]

    # 获取已经发言的玩家列表
    spoken_players = []
    for speech in conversation_history:
        if ":" in speech:
            speaker = speech.split(":")[0].strip()
            spoken_players.append(speaker)

    # 判断是否是第一轮发言
    is_first_round = len(conversation_history) == 0 and not player.active

    prompt = f"""你是狼人杀游戏中的 {player.name}，你的身份是 {player.role}。
    ## 游戏规则：
    - 阵营: {role_info["阵营"]}
    - 夜晚行动: {role_info["夜晚行动"]}
    - 胜利条件: {role_info["胜利条件"]}
    
    ## 当前游戏状态：
    {context}
    
    ## 已经发言的玩家：
    {', '.join(spoken_players) if spoken_players else '还没有人发言'}
    
    ## 你的行动记录：
    {', '.join(player.active) if player.active else '无'}
    
    ## 已发言玩家的发言记录：
    {conversation_history[-3:] if conversation_history else '无'}
    
    {'这是游戏第一轮发言，请进行开场发言。注意：第一轮发言要谨慎，不要妄下定论。' if is_first_round else '请只针对已经发言的玩家进行评论和分析。'}
    
    请注意：
    1. 只能评论已经发言过的玩家
    2. 不能提到还未发言的玩家
    3. 不能评论未发生的事情
    4. 字数控制在40字以内
    5. 保持逻辑合理性
    """

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是狼人杀游戏玩家，请根据实际情况发言，不要评论未发言的玩家。"},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"AI发言生成失败: {e}")
        return "让我思考一下当前的局势。"


# 启动游戏
if __name__ == "__main__":
    try:
        game = WerewolfGame()
        game.start()
    except Exception as e:
        print(f"程序运行时发生错误: {e}")
