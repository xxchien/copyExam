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
        self.school_id = kwargs.get('school_id', 5)
        self.authtoken = None

        # 使用不同属性设置 HTTP 标头。
        self.headers = {
            "Host": self.base_host,
            "XC-App-User-SchoolId": f"{self.base_school_id}",  # 学校 ID，可以稍后更改
            "AuthToken": f"{self.authtoken}"
        }

        # 配置日志记录。
        self.log_file = 'api_requests.log'
        self.log_level = logging.ERROR
        self.log_format = '%(asctime)s - %(levelname)s: %(message)s'

        # 限制并发数
        self.semaphore = asyncio.Semaphore(kwargs.get('max_concurrent_requests', 10))
        self.failed_students = []  # 用于记录失败的学生ID

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

    def login_to_school(self, **kwargs):
        self.base_envi = kwargs.get('base_envi', "xqdsj")
        self.school_id = kwargs.get('school_id', 7)

        username = kwargs.get('username', "13951078683@xuece")
        password = kwargs.get('password', "c50d98c79dbdb8049ab1571444771e68")

        self._update_headers()
        self.configure_logging()

        self.login_and_get_auth_token(username, password)
        self.switch_school()
        print(self.authtoken)

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
    def extract_data(data, **kwargs):
        """
        处理数据，找出英语科目
        :param data:
        :return:
        """
        course_code = kwargs.get("course_code", "ENGLISH")
        try:
            parsed_json = json.loads(data)
            # 遍历data列表，查找courseCode=ENGLISH的元素
            for item in parsed_json['data']:
                logging.info(f"正在寻找courseCode={course_code}的元素")
                if item['courseCode'] == course_code:
                    english_data = item
                    answercard = english_data['answercard']
                    exampaper = english_data['exampaper']
                    return [answercard, exampaper]
                else:
                    logging.error(f"未匹配courseCode={course_code}的元素")
            else:
                logging.error(f"JSON 数据中无courseCode={course_code}的元素")
                return None
        except json.JSONDecodeError as e:
            logging.error(f"JSON解析错误: {e}")
            return None
        except KeyError as e:
            logging.error(f"字段提取错误: {e}")
            return None

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
        :param session:
        :param exampaper_id:
        :param stu_id:
        :return: stu_img_url_list
        """
        url = f"{self.base_url}/api/examcenter/teacher/recognitionclient/exampaper/stu"
        params = {
            "exampaperId": exampaper_id,
            "stuUserId": stu_id,
        }

        async with self.semaphore:
            try:
                async with session.get(url, headers=self.headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data['data']['stuAnswerImgurls'].split("@##@")
                    else:
                        logging.error(f"请求失败，状态码为：{response.status}")
                        return None
            except Exception as e:
                logging.error(f"请求异常：{e}")

            logging.error(f"请求失败，学生ID: {stu_id} 达到最大重试次数")
            self.failed_students.append(stu_id)
            return None

    async def get_all_stu_answercards(self, exampaper_id, stu_list):
        async with aiohttp.ClientSession() as session:
            tasks = [self.get_stu_answercards(session, exampaper_id, stu['id']) for stu in stu_list]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            # 过滤掉 None 值
            return [url for sublist in results if sublist for url in sublist]

    @staticmethod
    async def download_image(session, url, save_directory):
        filename = os.path.join(save_directory, os.path.basename(url))
        try:
            async with session.get(url) as response:
                response.raise_for_status()
                with open(filename, 'wb') as f:
                    chunk = await response.content.read(1024)  # 初始读取
                    while chunk:
                        f.write(chunk)
                        chunk = await response.content.read(1024)  # 再次读取
            logging.info(f"Downloaded: {filename}")
        except Exception as e:
            logging.error(f"Failed to download {url}: {e}")

    async def async_download_images(self, url_list, save_directory):
        async with aiohttp.ClientSession() as session:
            tasks = [
                self.download_image(session, url, save_directory)
                for url in url_list
            ]
            for f in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Downloading images", unit="file"):
                await f

    def download_images(self, url_list, **kwargs):
        save_directory = kwargs.get('save_directory', os.getcwd())
        exam_name = kwargs.get('exam_name', 'images')
        save_directory = os.path.join(save_directory, exam_name)

        if not os.path.exists(save_directory):
            os.makedirs(save_directory)

        # 使用异步下载
        asyncio.run(self.async_download_images(url_list, save_directory))

    async def gather_urls(self, exampaper_id, stu_list, batch_size):
        url_list = []
        total_students = len(stu_list)
        with tqdm(total=total_students, unit="stu", desc="Fetching URLs") as pbar:
            for i in range(0, total_students, batch_size):
                try:
                    batch_stu_list = stu_list[i:i + batch_size]
                    urls = await self.get_all_stu_answercards(exampaper_id, batch_stu_list)
                    url_list.extend(urls)
                    # await asyncio.sleep(1)  # 每批次间隔
                    pbar.update(len(batch_stu_list))  # 更新进度条

                except Exception as e:
                    logging.error(f"重新登录！！！！！！！")
                    self.login_to_school()  # 重新登录
        return url_list

    def download_exam_images(self, **kwargs):
        """
        下载考试的所有学生答题卡图片。
        :param kwargs:
        :return: None
        """
        examination_id = kwargs.get('examination_id', 10211)
        batch_size = kwargs.get('batch_size', 10)
        max_students = kwargs.get('max_students')
        course_code = kwargs.get('course_code', 'ENGLISH')

        # 登录学校获取考试信息
        self.login_to_school(base_envi="xqdsj", school_id=self.school_id, username="13951078683@xuece",
                             password="c50d98c79dbdb8049ab1571444771e68")

        # 获取答题卡和考试详情
        data = self.get_answercard_detail(examination_id)
        datalist = self.extract_data(data, course_code=course_code)
        exampaper_id = datalist[1]['id']
        exam_info = self.get_examinfo(examination_id)
        exam_school_id_list = [school['schoolId'] for school in exam_info['schoolInfoList']]
        exam_school_id = exam_school_id_list[0]

        # 获取已上传答题卡的学生列表
        stu_list = self.get_stu_list(exampaper_id, exam_school_id, uploaded=True)
        if max_students:
            stu_list = stu_list[:max_students]

        # 使用 asyncio.run 运行异步 URL 获取并下载
        url_list = asyncio.run(self.gather_urls(exampaper_id, stu_list, batch_size))
        self.download_images(url_list, exam_name=datalist[1]['title'])
        logging.info("所有答题卡图片下载完成。")


if __name__ == "__main__":
    api = ApiRequest(school_id = 2)
    api.download_exam_images(examination_id=36300, course_code='ENGLISH')

# TODO: 目前后端做了接口限制，生产环境1min内限制接口数量450个，当出发接口限制时重新登录，换tokn
