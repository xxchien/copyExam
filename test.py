import asyncio
import os

import aiohttp
import requests
import json
import logging
from tqdm import tqdm


# 该代码定义了一个名为 "ApiRequest" 的类，用于进行 API 请求和执行特定操作。
class ApiRequest:

    # 构造函数 (__init__) 用于初始化类，并传入基础学校 ID。
    def __init__(self, **kwargs):
        # 设置环境和基础 URL。
        self.base_envi = kwargs.get('base_envi', "xqdsj")
        self.base_url = f"https://{self.base_envi}.xuece.cn"
        self.base_host = f"{self.base_envi}.xuece.cn"
        self.base_school_id = None
        self.school_id = kwargs.get('school_id', 7)
        self.authtoken = None

        # 使用不同属性设置 HTTP 标头。
        self.headers = {
            "Host": self.base_host,
            "XC-App-User-SchoolId": f"{self.base_school_id}",  # 学校 ID，可以稍后更改
            "AuthToken": f"{self.authtoken}"
        }

        # 配置日志记录。
        self.log_file = 'api_requests.log'
        self.log_level = logging.INFO
        self.log_format = '%(asctime)s - %(levelname)s: %(message)s'

    # 方法用于配置日志记录设置。
    def configure_logging(self):
        logging.basicConfig(filename=self.log_file, level=self.log_level, format=self.log_format)

    @staticmethod
    def update_headers_decorator(method):
        def wrapper(self, *args, **kwargs):
            result = method(self, *args, **kwargs)  # 执行原始方法
            self._update_headers()  # 更新 self.headers
            return result

        return wrapper

    # 私有方法：更新 self.headers
    def _update_headers(self):
        self.base_url = f"https://{self.base_envi}.xuece.cn"
        self.base_host = f"{self.base_envi}.xuece.cn"
        self.headers = {
            "Host": f"{self.base_envi}.xuece.cn",
            "XC-App-User-SchoolId": f"{self.base_school_id}",  # 学校 ID，可以稍后更改
            "AuthToken": f"{self.authtoken}"
        }

    # 切换学校的方法
    @update_headers_decorator
    def switch_school(self):
        if self.school_id == self.base_school_id:
            return 1

        school_id = self.school_id
        switch_url = f"{self.base_url}/api/usercenter/common/loginuserinfo/switchschool"
        data = {
            "schoolId": school_id,
            "clienttype": "BROWSER",
            "clientversion": "1.25.7"
        }

        try:

            response = requests.post(switch_url, headers=self.headers, data=data)
            response.raise_for_status()
            response_data = response.json()

            if "code" in response_data and response_data["code"] == "SUCCESS":
                self.base_school_id = self.school_id
                return response_data
            else:
                logging.error("切换学校失败：%s", str(response_data))
                raise Exception(f"切换学校失败：{str(response_data)}")
        except requests.exceptions.RequestException as e:
            logging.error("切换学校请求失败：%s", str(e))
            raise Exception(f"切换学校请求失败：{str(e)}")

    # 方法用于执行登录请求并获取身份验证令牌。
    @update_headers_decorator
    def login_and_get_auth_token(self, username, password):
        login_url = f"{self.base_url}/api/usercenter/nnauth/user/login"

        # 登录请求的参数。
        params = {
            "username": username,
            "encryptpwd": password,
            "clienttype": "BROWSER",
            "clientversion": "1.25.7",
            "systemversion": "chrome117.0.0.0"
        }

        try:
            response = requests.get(login_url, headers=self.headers, params=params)

            if response.status_code == 200:
                data = json.loads(response.content)
                if "data" in data and data["code"] == 'SUCCESS':
                    authtoken = data["data"]["authtoken"]
                    schoolid = data["data"]["user"]["schoolId"]
                    self.base_school_id = schoolid
                    self.authtoken = authtoken
                    return authtoken
                else:
                    logging.error("登录请求异常：%s", str(data))
                    raise Exception(f"登录请求异常：{str(data)}")
            else:
                logging.error("登录请求失败，状态码为：%d", response.status_code)
                raise Exception(f"登录请求失败，状态码为：{response.status_code}")
        except requests.exceptions.RequestException as e:
            logging.error("登录请求异常：%s", str(e))
            raise Exception(f"登录请求异常：{str(e)}")

    # 方法用于获取答题卡信息。
    def get_answercard_detail(self, examination_id):
        url = f"{self.base_url}/api/examcenter/teacher/answercard/getanswercardstatus?examinationId={examination_id}"

        try:
            response = requests.get(url, headers=self.headers)

            if response.status_code == 200:
                data = json.loads(response.content)
                data = json.dumps(data, indent=4, ensure_ascii=False)
                return data
            else:
                logging.error("请求失败，状态码为：%d", response.status_code)
                raise Exception(f"请求失败，状态码为：{response.status_code}")
        except requests.exceptions.RequestException as e:
            logging.error("请求异常：%s", str(e))
            raise Exception(f"请求异常：{str(e)}")

    @staticmethod
    def extract_data(data):
        """
        处理数据，找出英语科目
        :param data:
        :return:
        """
        try:
            parsed_json = json.loads(data)
            # 遍历data列表，查找courseCode=ENGLISH的元素
            for item in parsed_json['data']:
                print("正在寻找courseCode=ENGLISH的元素")
                if item['courseCode'] == 'ENGLISH':
                    english_data = item
                    answercard = english_data['answercard']
                    exampaper = english_data['exampaper']
                    return [answercard, exampaper]
                else:
                    print("未匹配courseCode=ENGLISH的元素")
            else:
                print("JSON 数据中无courseCode=ENGLISH的元素")
                return None
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
            return None
        except KeyError as e:
            print(f"字段提取错误: {e}")
            return None

    def get_ai_marking_info(self, exampaper_id):
        url = f"{self.base_url}/api/examcenter/ai/marking/task/getinfo?exampaperId={exampaper_id}"

        try:
            response = requests.get(url, headers=self.headers)

            if response.status_code == 200:
                data = json.loads(response.content)
                data = data['data']
                return data
            else:
                logging.error("请求失败，状态码为：%d", response.status_code)
                raise Exception(f"请求失败，状态码为：{response.status_code}")
        except requests.exceptions.RequestException as e:
            logging.error("请求异常：%s", str(e))
            raise Exception(f"请求异常：{str(e)}")

    @staticmethod
    def excute_marking_info(exampaper_id, marking_data, **kwargs):
        data_list = []
        for i in marking_data:
            data = {
                "exampaperId": exampaper_id,
                "id": kwargs.get('ai_marking_setting_id', None),
                "questionInfo": i['questionInfo'],
                "questionType": i['questionType'],
            }
            data_list.append(data.copy())
        return data_list

    def save_ai_marking_info(self, data):
        """
        保存智能批阅设置
        :param data: ID of the exam paper
        :return: ai_marking_setting_id
        """
        url = f"{self.base_url}/api/examcenter/ai/marking/task/saveinfo"

        try:
            response = requests.post(url, headers=self.headers, json=data)
            response.raise_for_status()
            response_data = response.json()

            if "code" in response_data and response_data["code"] == "SUCCESS":
                return response_data['data']['id']
            else:
                logging.error("智能批阅设置失败：%s", str(response_data))
                raise Exception(f"智能批阅设置失败：{str(response_data)}")
        except Exception as e:
            print("智能批阅设置失败：", str(e))

    def examin_create(self, exam_name):
        """
        用于创建考试
        :return:exam的id
        """
        import time
        # 获取当前时间的时间戳（单位：秒）
        timestamp = int(time.time() * 1000)

        examin_create_url = f"{self.base_url}/api/examcenter/teacher/exam/examinfocreate"

        data = {
            "examtypeCode": "HOMEWORK",
            "examDatetime": timestamp,
            "examName": exam_name,
            "gradeCode": "S03",  # 目前写死学校只能用一中高三
            "courseTypeCode[]": "ENGLISH",
            "classorgIdList[]": list(range(1862, 1880)) + [3432],
            # list(range(1222, 1231)),  list(range(1862, 1880)) + [3432],  # 目前写死学校只能用一中高三所有年级
            "schoolId": self.school_id,  # 目前写死学校只能用一中
            "courseRecommenders": {}
        }

        try:
            response = requests.post(examin_create_url, headers=self.headers, data=data)
            response.raise_for_status()
            response_data = response.json()

            if "code" in response_data and response_data["code"] == "SUCCESS":
                return response_data['data']['id']
            else:
                logging.error("创建考试失败：%s", str(response_data))
                raise Exception(f"创建考试失败：{str(response_data)}")
        except Exception as e:
            print("创建考试失败：", str(e))

    def get_examinfo(self, examination_id):
        """
        获取考试中考试信息
        :param examination_id:考试examid
        :return: exampaper的id
        """

        url = f"{self.base_url}/api/examcenter/teacher/exam/examinfo?examinationId={examination_id}"

        try:
            response = requests.get(url, headers=self.headers)

            if response.status_code == 200:
                data = json.loads(response.content)
                exam_info = data['data']
                return exam_info
            else:
                logging.error("请求失败，状态码为：%d", response.status_code)
                raise Exception(f"请求失败，状态码为：{response.status_code}")
        except requests.exceptions.RequestException as e:
            logging.error("请求异常：%s", str(e))
            raise Exception(f"请求异常：{str(e)}")

    def create_manually(self, exampaper_id):
        """
        创建答题卡
        :param exampaper_id:考试examid
        :return: code
        """

        url = f"{self.base_url}/api/examcenter/teacher/exam/manually/create"

        data = {
            "exampaperId": exampaper_id,
            "createMode": "MANUALLY"
        }

        try:
            response = requests.put(url, headers=self.headers, data=data)

            if response.status_code == 200:
                data = json.loads(response.content)
                code = data['code']
                return code
            else:
                logging.error("请求失败，状态码为：%d", response.status_code)
                raise Exception(f"请求失败，状态码为：{response.status_code}")
        except requests.exceptions.RequestException as e:
            logging.error("请求异常：%s", str(e))
            raise Exception(f"请求异常：{str(e)}")

    def update_structureseq(self, exampaper, exampaper_id):
        """
        保存答题卡题目结构，需要使用到exampaper中信息
        :return:
        """
        headers = self.headers
        headers["Content-Type"] = "application/json"

        update_structureseq_url = f"{self.base_url}/api/examcenter/teacher/exampaper/updatestructureseq"

        data = {
            "exampaperId": exampaper_id,
            "sectionInfoList": exampaper['sectionInfoList'],
            "title": exampaper['title']
        }

        data = json.dumps(data, indent=4, ensure_ascii=False)

        try:
            response = requests.post(update_structureseq_url, headers=headers, data=data)
            response.raise_for_status()
            response_data = response.json()

            if "code" in response_data and response_data["code"] == "SUCCESS":
                return response_data
            else:
                logging.error("1保存答题卡题目结构失败：%s", str(response_data))
                raise Exception(f"1保存答题卡题目结构失败：{str(response_data)}")
        except Exception as e:
            print("1保存答题卡题目结构失败：", str(e))

    def save_editinfo(self, answercard, exampaper_id):
        """
        保存答题卡位置结构，需要使用到answercard中信息
        :return:
        """
        headers = self.headers
        headers["Content-Type"] = "application/json"

        update_structureseq_url = f"{self.base_url}/api/examcenter/teacher/answercard/saveeditinfo"

        data = {
            "cutparamJsonstr": answercard['cutparamJsonstr'],
            "cutparamJsonstr2": answercard['cutparamJsonstr2'],
            "examPaperId": exampaper_id,
            "pageCount": answercard['pageCount'],
            "pageinfoJsonstr": answercard['pageinfoJsonstr'],
            "resetPdf": True,
            "scanMarking": answercard['scanMarking'],
            "sectionNumsInfo": answercard['sectionNumsInfo'],
            "templateJsonstr": answercard['templateJsonstr'],
        }

        data = json.dumps(data, indent=4, ensure_ascii=False)

        try:
            response = requests.post(update_structureseq_url, headers=headers, data=data)
            response.raise_for_status()
            response_data = response.json()

            if "code" in response_data and response_data["code"] == "SUCCESS":
                return response_data
            else:
                logging.error("2保存答题卡位置结构失败：%s", str(response_data))
                raise Exception(f"2保存答题卡位置结构失败：{str(response_data)}")
        except Exception as e:
            print("2保存答题卡位置结构失败：", str(e))

    def publish_answercard(self, answercard_id):
        """
        发布答题卡
        :param answercard_id: 答题卡ID
        :return: 发布结果
        """
        url = f"{self.base_url}/api/examcenter/teacher/answercard/publish"
        headers = {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/x-www-form-urlencoded",
            "authtoken": self.authtoken,
            "xc-app-user-schoolid": f"{self.school_id}"
        }
        data = {
            "answerCardId": answercard_id
        }

        try:
            response = requests.put(url, headers=headers, data=data)
            response.raise_for_status()
            response_data = response.json()

            if response_data.get("code") == "SUCCESS":
                return response_data
            else:
                logging.error("发布答题卡失败：%s", response_data)
                raise Exception(f"发布答题卡失败：{response_data}")

        except requests.exceptions.RequestException as e:
            logging.error("请求异常：%s", str(e))
            raise Exception(f"请求异常：{str(e)}")

    def get_stu_list(self, exampaper_id, exam_school_id, **kwargs):
        """
        获取学生列表
        :param exampaper_id: 考试试卷 ID
        :param exam_school_id: 学校 ID
        :param kwargs: 其他可选参数，例如 uploaded
        :return: 学生列表 (stu_list)
        """
        # 构建请求的 URL 和参数
        url = f"{self.base_url}/api/examcenter/teacher/recognitionclient/class/namelist"
        params = {
            "exampaperId": exampaper_id,
            "schoolId": exam_school_id,
        }

        try:
            # 发送 GET 请求并检查响应状态
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()  # 自动抛出异常，如果状态码不为 200

            # 解析返回的数据
            data = response.json().get('data', [])

            # 合并所有班级的学生列表
            stu_list = []
            for exam_class in data:
                stu_list.extend(exam_class.get('stuList', []))

            # 根据 uploaded 参数进行筛选（如果提供）
            uploaded = kwargs.get('uploaded')
            if uploaded is not None:
                stu_list = [stu for stu in stu_list if stu.get("uploaded") == uploaded]

            return stu_list

        except requests.exceptions.RequestException as e:
            logging.error("请求异常：%s", str(e))
            raise Exception(f"请求异常：{str(e)}")
        except json.JSONDecodeError as e:
            logging.error("JSON 解析错误：%s", str(e))
            raise Exception(f"JSON 解析错误：{str(e)}")

    async def get_stu_answercards(self, session, exampaper_id, stu_id):
        """
        获取学生的试卷url
        :param exampaper_id:
        :param stu_id:
        :return: stu_img_url_list
        """
        url = f"{self.base_url}/api/examcenter/teacher/recognitionclient/exampaper/stu"
        params = {
            "exampaperId": exampaper_id,
            "stuUserId": stu_id,
        }

        try:
            async with session.get(url, headers=self.headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    stu_img_urls = data['data']['stuAnswerImgurls']
                    stu_img_url_list = stu_img_urls.split("@##@")
                    return stu_img_url_list
                else:
                    logging.error("请求失败，状态码为：%d", response.status)
                    raise Exception(f"请求失败，状态码为：{response.status}")
        except requests.exceptions.RequestException as e:
            logging.error("请求异常：%s", str(e))
            raise Exception(f"请求异常：{str(e)}")

    async def get_all_stu_answercards(self, exampaper_id, stu_list):
        async with aiohttp.ClientSession() as session:
            tasks = [self.get_stu_answercards(session, exampaper_id, stu['id']) for stu in stu_list]
            results = await asyncio.gather(*tasks)
            return [url for sublist in results for url in sublist]

    @staticmethod
    def download_images(url_list, **kwargs):
        """
        下载图片的函数，从给定的 URL 列表中下载图片
        :param url_list:
        :param kwargs:
        :return:
        """
        # 从 kwargs 中获取保存目录，如果未提供则默认为当前工作目录
        save_directory = kwargs.get('save_directory', os.getcwd())
        exam_name = kwargs.get('exam_name')

        # 如果提供了考试名称，则创建以考试名称为子目录的保存路径
        if exam_name:
            save_directory = os.path.join(save_directory, exam_name)
        else:
            # 如果未提供考试名称，则创建默认的 'images' 文件夹来保存图片
            save_directory = os.path.join(save_directory, 'images')

        # 如果保存目录不存在，则创建该目录
        if not os.path.exists(save_directory):
            os.makedirs(save_directory)

        # 遍历 URL 列表，下载每张图片，使用 tqdm 显示总进度
        with tqdm(total=len(url_list), unit='file', desc='Downloading images') as pbar:
            for url in url_list:
                # 从 URL 中提取文件名，并创建完整的文件路径
                filename = os.path.join(save_directory, os.path.basename(url))
                try:
                    # 发送 GET 请求，使用 stream 模式以便逐步读取内容
                    response = requests.get(url, stream=True, timeout=10)
                    response.raise_for_status()  # 检查请求是否成功（状态码 200）
                    total_size = int(response.headers.get('content-length', 0))  # 获取文件总大小
                    # 打开文件并以二进制模式写入内容，同时显示下载进度
                    with open(filename, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=1024):
                            if chunk:  # 写入文件并更新进度条
                                f.write(chunk)
                    # 记录成功下载的日志
                    logging.info(f"Downloaded: {filename}")
                except requests.exceptions.RequestException as e:
                    # 如果下载失败，记录错误日志
                    logging.error(f"Failed to download {url}: {e}")
                finally:
                    # 更新 tqdm 进度条
                    pbar.update(1)

    def download_exam_images(self, **kwargs):
        """
        下载考试的所有学生答题卡图片。
        :param kwargs:
        :return: None
        """
        examination_id = 20680

        batch_size = kwargs.get('batch_size', 50)
        max_students = kwargs.get('max_students')

        # 设置基础信息
        self.base_envi = "xqdsj"
        self.school_id = 7

        username = "market03"
        password = "67391ff79276f08ec5934bc99787eb4e"

        # 更新请求头和日志
        self._update_headers()
        self.configure_logging()

        # 登录并切换学校
        self.login_and_get_auth_token(username, password)
        self.switch_school()

        # 获取答题卡详情
        data = self.get_answercard_detail(examination_id)
        datalist = self.extract_data(data)

        exampaper_data = datalist[1]
        exampaper_id = exampaper_data['id']

        # 获取考试信息
        exam_info = self.get_examinfo(examination_id)
        exam_school_list = exam_info['schoolInfoList']
        exam_school_id_list = [school['schoolId'] for school in exam_school_list]

        # 取第一个学校的 ID
        exam_school_id = exam_school_id_list[0]

        # 获取已上传答题卡的学生列表
        stu_list = self.get_stu_list(exampaper_id, exam_school_id, uploaded=True)

        # 如果设置了最大学生数量，则截取学生列表
        if max_students is not None:
            stu_list = stu_list[:max_students]

        # 分批次处理学生列表，避免一次性处理过多学生导致内存不足
        total_students = len(stu_list)
        url_list = []


        for i in range(0, total_students, batch_size):
            batch_stu_list = stu_list[i:i + batch_size]
            urls = asyncio.run(self.get_all_stu_answercards(exampaper_id, batch_stu_list))
            url_list.extend(urls)
            self.download_images(url_list, exam_name=datalist[1]['title'])
            url_list.clear()  # 每次下载完成后清空

        print("所有答题卡图片下载完成。")


if __name__ == "__main__":
    api = ApiRequest()
    api.download_exam_images(max_students=200)
