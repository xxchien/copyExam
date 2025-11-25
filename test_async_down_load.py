import asyncio
import os
import time
import functools

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

        # 登录凭据保存，用于重新登录
        self.login_credentials = {
            'username': kwargs.get('username', "13951078683@xuece"),
            'password': kwargs.get('password', "c50d98c79dbdb8049ab1571444771e68"),
            'base_envi': self.base_envi,
            'school_id': self.school_id
        }

        # 使用不同属性设置 HTTP 标头。
        self.headers = {
            "Host": self.base_host,
            "XC-App-User-SchoolId": f"{self.base_school_id}",  # 学校 ID，可以稍后更改
            "AuthToken": f"{self.authtoken}"
        }

        # 配置日志记录。
        self.log_file = 'api_requests.log'
        self.log_level = logging.INFO  # 改为INFO级别以便更好地追踪
        self.log_format = '%(asctime)s - %(levelname)s: %(message)s'

        # 限制并发数 - 减少并发数以降低429错误概率
        self.semaphore = asyncio.Semaphore(kwargs.get('max_concurrent_requests', 5))
        self.failed_students = []  # 用于记录失败的学生ID
        self.no_data_students = []  # 用于记录没有答题卡数据的学生ID
        self.success_students = []  # 用于记录成功获取数据的学生ID

        # 接口限制相关 - 改进的锁机制
        self.rate_limit_detected = False
        self.rate_limit_lock = asyncio.Lock()
        self.login_in_progress = False
        self.token_update_event = asyncio.Event()
        self.token_update_event.set()  # 初始状态为可用

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
        logging.info(f"Headers已更新，新的AuthToken: {self.authtoken}")

    # 生成当前headers的方法，确保每次都使用最新的token
    def _get_current_headers(self):
        """获取包含最新token的headers"""
        return {
            "Host": f"{self.base_envi}.xuece.cn",
            "XC-App-User-SchoolId": f"{self.base_school_id}",
            "AuthToken": f"{self.authtoken}"
        }

    # 检查是否触发了接口限制
    def _is_rate_limited(self, response_data):
        """
        检查响应是否表示接口限制
        根据实际API返回的错误码或消息进行判断
        """
        if response_data is None:
            return False

        if isinstance(response_data, dict):
            # 常见的接口限制标识
            rate_limit_indicators = [
                'rate limit',
                'too many requests',
                '请求过于频繁',
                '接口限制',
                'limit exceeded',
                '450'
            ]

            # 检查错误码和消息
            code = str(response_data.get('code', '')).lower()
            message = str(response_data.get('message', '')).lower()

            for indicator in rate_limit_indicators:
                if indicator in code or indicator in message:
                    return True

        return False

    async def _handle_rate_limit_and_retry(self):
        """
        处理接口限制：重新登录并等待 - 改进版本
        """
        async with self.rate_limit_lock:
            # 如果已经有其他协程在处理登录，则等待
            if self.login_in_progress:
                logging.info("其他协程正在处理登录，等待完成...")
                await self.token_update_event.wait()
                return

            # 开始登录流程
            self.login_in_progress = True
            self.token_update_event.clear()  # 阻止其他协程继续

            try:
                old_token = self.authtoken
                logging.warning("检测到接口限制，开始重新登录...")

                # 使用 functools.partial 来正确传递关键字参数
                login_func = functools.partial(self.login_to_school, **self.login_credentials)
                await asyncio.get_event_loop().run_in_executor(None, login_func)

                # 重新登录后立即更新headers
                self._update_headers()

                logging.info(f"重新登录成功，Token已更新: {old_token} -> {self.authtoken}")
                logging.info("等待3秒后继续...")

                # 等待3秒，让服务器缓解压力
                await asyncio.sleep(3)

                # 重置标志
                self.rate_limit_detected = False
                logging.info("等待结束，继续进行异步操作")

            except Exception as e:
                logging.error(f"重新登录失败: {e}")
                self.rate_limit_detected = False
                raise
            finally:
                # 无论成功失败，都要重置状态并通知等待的协程
                self.login_in_progress = False
                self.token_update_event.set()

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
                    logging.info(f"登录成功，获得新Token: {authtoken}")
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
        self.base_envi = kwargs.get('base_envi', self.login_credentials['base_envi'])
        self.school_id = kwargs.get('school_id', self.login_credentials['school_id'])

        username = kwargs.get('username', self.login_credentials['username'])
        password = kwargs.get('password', self.login_credentials['password'])

        # 更新登录凭据
        self.login_credentials.update({
            'username': username,
            'password': password,
            'base_envi': self.base_envi,
            'school_id': self.school_id
        })

        self._update_headers()
        self.configure_logging()

        self.login_and_get_auth_token(username, password)
        self.switch_school()
        print(f"登录成功，Token: {self.authtoken}")

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

    async def get_stu_answercards(self, session, exampaper_id, stu_id, max_retries=3):
        """
        获取学生的试卷url (改进版本，更好的错误处理和重试机制)
        :param session:
        :param exampaper_id:
        :param stu_id:
        :param max_retries: 最大重试次数，减少到3次
        :return: stu_img_url_list 或 None
        """
        url = f"{self.base_url}/api/examcenter/teacher/recognitionclient/exampaper/stu"
        params = {
            "exampaperId": exampaper_id,
            "stuUserId": stu_id,
        }

        async with self.semaphore:
            retry_count = 0
            last_error = None

            while retry_count < max_retries:
                try:
                    # 等待Token更新完成
                    await self.token_update_event.wait()

                    # 使用最新的headers
                    current_headers = self._get_current_headers()

                    # 增加请求超时时间
                    timeout = aiohttp.ClientTimeout(total=60)

                    async with session.get(url, headers=current_headers, params=params, timeout=timeout) as response:
                        if response.status == 200:
                            try:
                                data = await response.json()
                                logging.debug(f"学生ID {stu_id}: 收到响应数据")
                            except Exception as json_error:
                                last_error = f"JSON解析失败: {json_error}"
                                logging.error(f"学生ID {stu_id}: {last_error}")
                                retry_count += 1
                                await asyncio.sleep(2)  # 等待2秒后重试
                                continue

                            # 检查是否触发接口限制
                            if self._is_rate_limited(data):
                                logging.warning(f"学生ID {stu_id}: 检测到接口限制，准备重新登录")
                                await self._handle_rate_limit_and_retry()
                                retry_count += 1
                                continue

                            # 数据验证
                            if not isinstance(data, dict) or 'data' not in data:
                                last_error = "响应数据格式异常"
                                logging.warning(f"学生ID {stu_id}: {last_error}")
                                retry_count += 1
                                await asyncio.sleep(2)
                                continue

                            if data['data'] is None:
                                logging.info(f"学生ID {stu_id}: 数据为空，可能未上传答题卡")
                                self.no_data_students.append(stu_id)
                                return None

                            if not isinstance(data['data'], dict) or 'stuAnswerImgurls' not in data['data']:
                                last_error = "数据结构异常"
                                logging.warning(f"学生ID {stu_id}: {last_error}")
                                retry_count += 1
                                await asyncio.sleep(2)
                                continue

                            img_urls = data['data']['stuAnswerImgurls']
                            if not img_urls:
                                logging.info(f"学生ID {stu_id}: 答题卡图片URL为空")
                                self.no_data_students.append(stu_id)
                                return None

                            # 成功获取数据
                            url_list = img_urls.split("@##@")
                            logging.info(f"学生ID {stu_id}: 成功获取 {len(url_list)} 张答题卡图片")
                            self.success_students.append(stu_id)
                            return url_list

                        elif response.status == 429:  # HTTP 429 Too Many Requests
                            last_error = "HTTP 429 - 请求过于频繁"
                            logging.warning(f"学生ID {stu_id}: {last_error}")
                            await self._handle_rate_limit_and_retry()
                            retry_count += 1
                            continue
                        else:
                            response_text = await response.text()
                            last_error = f"请求失败，状态码：{response.status}"
                            logging.error(f"学生ID {stu_id}: {last_error}")
                            retry_count += 1

                except asyncio.TimeoutError:
                    last_error = "请求超时"
                    logging.error(f"学生ID {stu_id}: {last_error}")
                    retry_count += 1
                except Exception as e:
                    last_error = f"请求异常：{e}"
                    logging.error(f"学生ID {stu_id}: {last_error}")
                    retry_count += 1

                if retry_count < max_retries:
                    # 渐进式退避，每次重试等待时间递增
                    wait_time = min(2 * retry_count, 10)
                    logging.info(f"学生ID {stu_id}: 重试 {retry_count + 1}/{max_retries}，等待 {wait_time} 秒")
                    await asyncio.sleep(wait_time)

            # 达到最大重试次数
            logging.error(f"学生ID {stu_id}: 达到最大重试次数，最后错误: {last_error}")
            self.failed_students.append({'id': stu_id, 'error': last_error})
            return None

    async def get_all_stu_answercards(self, exampaper_id, stu_list):
        # 增加连接超时时间
        timeout = aiohttp.ClientTimeout(total=300, connect=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            tasks = [self.get_stu_answercards(session, exampaper_id, stu['id']) for stu in stu_list]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 过滤掉 None 值和异常
            valid_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logging.error(f"任务执行异常 (学生ID {stu_list[i]['id']}): {result}")
                    self.failed_students.append({'id': stu_list[i]['id'], 'error': str(result)})
                elif result is not None:
                    valid_results.extend(result)

            return valid_results

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
        processed_students = 0

        with tqdm(total=total_students, unit="stu", desc="Fetching URLs") as pbar:
            for i in range(0, total_students, batch_size):
                try:
                    batch_stu_list = stu_list[i:i + batch_size]

                    # 获取当前批次的URLs
                    urls = await self.get_all_stu_answercards(exampaper_id, batch_stu_list)
                    url_list.extend(urls)

                    processed_students += len(batch_stu_list)
                    pbar.update(len(batch_stu_list))

                    # 批次间适当延迟，避免请求过于频繁
                    if i + batch_size < total_students:
                        await asyncio.sleep(1)  # 增加批次间延迟

                except Exception as e:
                    logging.error(f"批次处理失败 (学生 {i}-{i + batch_size}): {e}")

        # 详细的统计信息
        success_count = len(self.success_students)
        no_data_count = len(self.no_data_students)
        failed_count = len(self.failed_students)

        logging.info(f"URL获取完成统计:")
        logging.info(f"  成功获取: {success_count} 个学生")
        logging.info(f"  无数据/未上传: {no_data_count} 个学生")
        logging.info(f"  失败: {failed_count} 个学生")
        logging.info(f"  总URL数量: {len(url_list)}")

        print(f"\n=== 答题卡获取统计 ===")
        print(f"成功获取: {success_count} 个学生")
        print(f"无数据/未上传: {no_data_count} 个学生")
        print(f"失败: {failed_count} 个学生")
        print(f"总URL数量: {len(url_list)}")

        if self.failed_students:
            print(f"\n失败的学生详情:")
            for failure in self.failed_students:
                if isinstance(failure, dict):
                    print(f"  学生ID {failure['id']}: {failure['error']}")
                else:
                    print(f"  学生ID {failure}: 未知错误")

        if self.no_data_students:
            logging.info(f"无数据的学生ID: {self.no_data_students}")

        return url_list

    def download_exam_images(self, **kwargs):
        """
        下载考试的所有学生答题卡图片。
        :param kwargs:
        :return: None
        """
        examination_id = kwargs.get('examination_id', 10211)
        batch_size = kwargs.get('batch_size', 5)  # 减少批次大小
        max_students = kwargs.get('max_students')
        course_code = kwargs.get('course_code', 'ENGLISH')

        # 清空之前的记录
        self.failed_students = []
        self.no_data_students = []
        self.success_students = []

        # 登录学校获取考试信息
        self.login_to_school(base_envi="xqdsj", school_id=7, username="13951078683@xuece",
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

        print(f"总共需要处理 {len(stu_list)} 个学生的答题卡")

        # 使用 asyncio.run 运行异步 URL 获取并下载
        url_list = asyncio.run(self.gather_urls(exampaper_id, stu_list, batch_size))

        if url_list:
            self.download_images(url_list, exam_name=datalist[1]['title'])
            logging.info("所有答题卡图片下载完成。")
            print(f"\n下载完成！共下载 {len(url_list)} 张图片")
        else:
            logging.warning("没有获取到任何图片URL")
            print("警告：没有获取到任何图片URL")


if __name__ == "__main__":
    api = ApiRequest()
    api.download_exam_images(examination_id=34172, course_code='ENGLISH')
