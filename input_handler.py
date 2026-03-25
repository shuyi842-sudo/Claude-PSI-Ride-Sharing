"""
多模态输入处理器

支持语音转文本、地图选点转地址、目的地预测等功能。
"""

import json
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class AddressSuggestion:
    """地址建议"""
    text: str
    lng: float
    lat: float
    score: float
    source: str  # 'geocode', 'history', 'favorite'


@dataclass
class VoiceInput:
    """语音输入结果"""
    text: str
    confidence: float
    language: str = "zh-CN"


@dataclass
class DestinationPrediction:
    """目的地预测"""
    address: str
    lng: float
    lat: float
    reason: str
    probability: float


class InputHandler:
    """
    多模态输入处理器

    功能：
    - 语音转文本（集成API）
    - 地图选点转地址（逆地理编码）
    - 智能目的地推荐
    - 地址解析和补全
    """

    def __init__(self, amap_key: str = None):
        """
        初始化输入处理器

        Args:
            amap_key: 高德地图API Key
        """
        if amap_key is None:
            from config import Config
            amap_key = Config.AMAP_KEY

        self.amap_key = amap_key
        self.user_history: Dict[str, List[Dict]] = {}  # {user_id: [trips]}
        self.user_favorites: Dict[str, List[Dict]] = {}  # {user_id: [favorites]}

    def voice_to_text(self, audio_data: bytes, language: str = "zh-CN") -> VoiceInput:
        """
        语音转文本

        Args:
            audio_data: 音频数据（bytes）
            language: 语言代码（如 "zh-CN", "en-US"）

        Returns:
            VoiceInput对象

        注意：
        实际生产中需要集成语音识别API（如讯飞、百度、Google Speech等）
        这里提供简化实现框架。
        """
        # 这里是简化实现，实际需要调用语音识别API
        # 示例：调用百度语音识别API
        # response = requests.post(
        #     'https://vop.baidu.com/server_api',
        #     params={'dev_pid': 1537, 'cuid': 'your_device_id', 'token': 'your_token'},
        #     data=audio_data,
        #     headers={'Content-Type': 'audio/wav; rate=16000'}
        # )

        # 简化实现：返回模拟数据
        return VoiceInput(
            text="从中关村到北京西站",
            confidence=0.95,
            language=language
        )

    def map_select_to_address(self, lng: float, lat: float) -> Optional[str]:
        """
        地图选点转地址（逆地理编码）

        Args:
            lng: 经度
            lat: 纬度

        Returns:
            地址字符串，失败时返回None
        """
        if not self.amap_key:
            return None

        try:
            import requests

            url = "https://restapi.amap.com/v3/geocode/regeo"
            params = {
                'location': f"{lng},{lat}",
                'key': self.amap_key,
                'output': 'json',
                'extensions': 'all'
            }

            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if data.get('status') == '1':
                    regeocode = data.get('regeocode', {})
                    # 优先返回详细地址
                    formatted_address = regeocode.get('formatted_address')
                    if formatted_address:
                        return formatted_address
                    # 回退到组件地址
                    address_component = regeocode.get('addressComponent', {})
                    parts = [
                        address_component.get('province'),
                        address_component.get('city'),
                        address_component.get('district'),
                        address_component.get('township')
                    ]
                    return " ".join(filter(None, parts))

        except Exception as e:
            print(f"逆地理编码失败: {e}")

        return None

    def predict_destination(self, partial_input: str, user_id: str,
                          context: Dict = None) -> List[DestinationPrediction]:
        """
        预测目的地（基于历史数据）

        Args:
            partial_input: 部分输入（如"中关"）
            user_id: 用户ID
            context: 上下文信息（时间、当前位置等）

        Returns:
            预测列表，按概率降序排列
        """
        predictions = []

        # 1. 基于用户历史
        if user_id in self.user_history:
            history = self.user_history[user_id]
            for trip in history:
                destination = trip.get('end')
                if partial_input.lower() in destination.lower():
                    predictions.append(DestinationPrediction(
                        address=destination,
                        lng=trip.get('end_lng', 0),
                        lat=trip.get('end_lat', 0),
                        reason="基于历史记录",
                        probability=0.8
                    ))

        # 2. 基于收藏地址
        if user_id in self.user_favorites:
            favorites = self.user_favorites[user_id]
            for fav in favorites:
                address = fav.get('address')
                if partial_input.lower() in address.lower():
                    predictions.append(DestinationPrediction(
                        address=address,
                        lng=fav.get('lng', 0),
                        lat=fav.get('lat', 0),
                        reason="收藏地址",
                        probability=0.9
                    ))

        # 3. 基于当前时间和地理位置的热门地点
        if context and 'current_lat' in context and 'current_lng' in context:
            nearby = self._get_nearby_popular_places(
                context['current_lng'],
                context['current_lat']
            )
            for place in nearby:
                if partial_input.lower() in place['name'].lower():
                    predictions.append(DestinationPrediction(
                        address=place['name'],
                        lng=place['lng'],
                        lat=place['lat'],
                        reason="附近热门地点",
                        probability=0.7
                    ))

        # 去重并排序
        seen = set()
        unique_predictions = []
        for pred in predictions:
            key = pred.address
            if key not in seen:
                seen.add(key)
                unique_predictions.append(pred)

        # 按概率排序
        unique_predictions.sort(key=lambda p: p.probability, reverse=True)

        return unique_predictions[:5]  # 返回前5个

    def _get_nearby_popular_places(self, lng: float, lat: float,
                                   radius: int = 2000) -> List[Dict]:
        """
        获取附近热门地点

        Args:
            lng, lat: 中心坐标
            radius: 搜索半径（米）

        Returns:
            热门地点列表
        """
        if not self.amap_key:
            return []

        try:
            import requests

            url = "https://restapi.amap.com/v3/place/around"
            params = {
                'location': f"{lng},{lat}",
                'key': self.amap_key,
                'keywords': '地铁站|机场|火车站|商场|医院|学校',
                'radius': radius,
                'sort': 'weight',
                'output': 'json'
            }

            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if data.get('status') == '1':
                    pois = data.get('pois', [])
                    return [
                        {
                            'name': poi.get('name'),
                            'lng': float(poi.get('location', ',').split(',')[0]),
                            'lat': float(poi.get('location', ',').split(',')[1])
                        }
                        for poi in pois[:10]
                    ]

        except Exception as e:
            print(f"搜索附近地点失败: {e}")

        return []

    def add_user_history(self, user_id: str, trip: Dict):
        """
        添加用户历史行程

        Args:
            user_id: 用户ID
            trip: 行程数据
        """
        if user_id not in self.user_history:
            self.user_history[user_id] = []

        self.user_history[user_id].append(trip)

        # 保留最近100条记录
        if len(self.user_history[user_id]) > 100:
            self.user_history[user_id] = self.user_history[user_id][-100:]

    def add_user_favorite(self, user_id: str, address: str,
                        lng: float, lat: float, name: str = None):
        """
        添加用户收藏地址

        Args:
            user_id: 用户ID
            address: 地址
            lng, lat: 坐标
            name: 自定义名称
        """
        if user_id not in self.user_favorites:
            self.user_favorites[user_id] = []

        self.user_favorites[user_id].append({
            'address': address,
            'lng': lng,
            'lat': lat,
            'name': name or address
        })

        # 最多保留50个收藏
        if len(self.user_favorites[user_id]) > 50:
            self.user_favorites[user_id] = self.user_favorites[user_id][-50:]

    def get_suggestions(self, query: str, user_id: str,
                     current_lng: float = None, current_lat: float = None) -> List[AddressSuggestion]:
        """
        获取地址建议

        Args:
            query: 查询字符串
            user_id: 用户ID
            current_lng, current_lat: 当前位置

        Returns:
            地址建议列表
        """
        suggestions = []

        # 1. 基于高德API的地理编码建议
        if self.amap_key:
            api_suggestions = self._get_geocode_suggestions(query)
            suggestions.extend(api_suggestions)

        # 2. 基于用户历史
        if user_id in self.user_history:
            for trip in self.user_history[user_id]:
                for field in ['start', 'end']:
                    address = trip.get(field)
                    if address and query.lower() in address.lower():
                        suggestions.append(AddressSuggestion(
                            text=address,
                            lng=trip.get(f'{field}_lng', 0),
                            lat=trip.get(f'{field}_lat', 0),
                            score=0.7,
                            source='history'
                        ))

        # 3. 基于收藏
        if user_id in self.user_favorites:
            for fav in self.user_favorites[user_id]:
                address = fav.get('address')
                if address and query.lower() in address.lower():
                    suggestions.append(AddressSuggestion(
                        text=fav.get('name', address),
                        lng=fav.get('lng', 0),
                        lat=fav.get('lat', 0),
                        score=0.8,
                        source='favorite'
                    ))

        # 4. 考虑距离因素
        if current_lng is not None and current_lat is not None:
            for sug in suggestions:
                sug.score *= self._calculate_distance_weight(
                    current_lng, current_lat, sug.lng, sug.lat
                )

        # 去重和排序
        seen = set()
        unique_suggestions = []
        for sug in suggestions:
            key = f"{sug.text}:{sug.lng}:{sug.lat}"
            if key not in seen:
                seen.add(key)
                unique_suggestions.append(sug)

        unique_suggestions.sort(key=lambda s: s.score, reverse=True)

        return unique_suggestions[:10]

    def _get_geocode_suggestions(self, query: str) -> List[AddressSuggestion]:
        """从高德API获取地理编码建议"""
        if not self.amap_key:
            return []

        try:
            import requests

            url = "https://restapi.amap.com/v3/assistant/inputtips"
            params = {
                'keywords': query,
                'key': self.amap_key,
                'output': 'json',
                'city': '全国',
                'citylimit': 'false'
            }

            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if data.get('status') == '1':
                    tips = data.get('tips', [])
                    return [
                        AddressSuggestion(
                            text=tip.get('name') or tip.get('district'),
                            lng=float(tip.get('location', ',0').split(',')[0] or 0),
                            lat=float(tip.get('location', '0,').split(',')[1] or 0),
                            score=1.0 - tip.get('distance', 0) / 100000,  # 距离越近分数越高
                            source='geocode'
                        )
                        for tip in tips if tip.get('location')
                    ]

        except Exception as e:
            print(f"获取地理编码建议失败: {e}")

        return []

    def _calculate_distance_weight(self, lng1: float, lat1: float,
                                lng2: float, lat2: float) -> float:
        """
        计算距离权重

        距离越近权重越高

        Args:
            lng1, lat1: 第一个点
            lng2, lat2: 第二个点

        Returns:
            权重值 (0.5 - 1.0)
        """
        import math
        R = 6371000  # 地球半径（米）

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lng = math.radians(lng2 - lng1)

        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lng / 2) ** 2)
        c = 2 * math.asin(math.sqrt(a))

        distance = R * c

        # 距离权重：1km内权重1，10km外权重0.5
        if distance < 1000:
            return 1.0
        elif distance < 10000:
            return 1.0 - (distance - 1000) / 18000
        else:
            return 0.5

    def parse_route_command(self, text: str) -> Optional[Dict[str, str]]:
        """
        解析路线命令文本

        支持的格式：
        - "从A到B"
        - "A到B"
        - "去B"
        - "到B"
        - "A -> B"

        Args:
            text: 输入文本

        Returns:
            解析结果 {'from': 'A', 'to': 'B'}
        """
        # 正则表达式匹配各种格式
        patterns = [
            r'从\s*(.+?)\s*到\s*(.+)',  # "从A到B"
            r'(.+?)\s*到\s*(.+)',      # "A到B"
            r'(?:去|前往)\s*(.+)',     # "去B"
            r'(?:到)\s*(.+)',          # "到B"
            r'(.+?)\s*->\s*(.+)',      # "A -> B"
        ]

        for pattern in patterns:
            match = re.match(pattern, text.strip())
            if match:
                groups = match.groups()
                if len(groups) == 2:
                    return {'from': groups[0].strip(), 'to': groups[1].strip()}
                elif len(groups) == 1:
                    return {'to': groups[0].strip()}

        return None

    def get_user_stats(self, user_id: str) -> Dict:
        """
        获取用户输入统计

        Args:
            user_id: 用户ID

        Returns:
            统计信息
        """
        history = self.user_history.get(user_id, [])
        favorites = self.user_favorites.get(user_id, [])

        # 统计常去地点
        destinations = {}
        for trip in history:
            dest = trip.get('end')
            if dest:
                destinations[dest] = destinations.get(dest, 0) + 1

        top_destinations = sorted(
            destinations.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]

        return {
            'total_trips': len(history),
            'total_favorites': len(favorites),
            'top_destinations': [{'address': d, 'count': c} for d, c in top_destinations]
        }


# 全局实例
_input_handler: Optional[InputHandler] = None


def get_input_handler(amap_key: str = None) -> InputHandler:
    """获取输入处理器实例（单例）"""
    global _input_handler
    if _input_handler is None:
        _input_handler = InputHandler(amap_key)
    return _input_handler
