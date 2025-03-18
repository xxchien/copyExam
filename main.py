import asyncio
import os
import time

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
        self.base_envi = kwargs.get('base_envi', "xqdsj.xuece.cn")
        self.base_url = f"https://{self.base_envi}"
        self.base_host = f"{self.base_envi}"
        self.base_school_id = None
        self.school_id = kwargs.get('school_id', 7)
        self.target_school_id = kwargs.get('target_school_id', 63)
        self.grade_code = kwargs.get('grade_code', 'S01')
        self.exam_course = kwargs.get('exam_course', 'ENGLISH')
        self.authtoken = None

        # 使用不同属性设置 HTTP 标头。
        self.headers = {
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
        self.base_url = f"https://{self.base_envi}"
        self.base_host = f"{self.base_envi}"
        self.headers = {
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
    def extract_exam_course_list(data):
        """
        处理数据，找出英语科目
        :param data:
        :return:
        """
        try:
            exam_course_list = []
            parsed_json = json.loads(data)
            for item in parsed_json['data']:
                exam_course_list.append(item['courseCode'])
            else:
                logging.error("考试中无学科")
            return exam_course_list
        except json.JSONDecodeError as e:
            logging.error(f"JSON解析错误: {e}")
            return None
        except KeyError as e:
            logging.error(f"字段提取错误: {e}")
            return None

    def extract_data(self, data, **kwargs):
        """
        处理数据，找出英语科目
        :param data:
        :return:
        """
        try:
            parsed_json = json.loads(data)
            exam_course = kwargs.get('exam_course', self.exam_course)
            for item in parsed_json['data']:
                print(f"正在寻找courseCode={exam_course}的元素")
                if item['courseCode'] == exam_course:
                    exam_course_data = item
                    answercard = exam_course_data['answercard']
                    exampaper = exam_course_data['exampaper']
                    return [answercard, exampaper]
                else:
                    logging.error("未匹配courseCode=ENGLISH的元素")
            else:
                logging.error("JSON 数据中无courseCode=ENGLISH的元素")
                return None
        except json.JSONDecodeError as e:
            logging.error(f"JSON解析错误: {e}")
            return None
        except KeyError as e:
            logging.error(f"字段提取错误: {e}")
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
                "compositionSettingInfo": i["compositionSettingInfo"],
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

    def examin_create(self, exam_name, **kwargs):
        """
        用于创建考试
        :return:exam的id
        """

        import time
        classorg_list = self.get_classorg_list()
        # 获取当前时间的时间戳（单位：秒）
        timestamp = int(time.time() * 1000)

        course_list = kwargs.get('exam_course_list', [self.exam_course])

        examin_create_url = f"{self.base_url}/api/examcenter/teacher/exam/examinfocreate"

        data = {
            "examtypeCode": "HOMEWORK",
            "examDatetime": timestamp,
            "examName": exam_name,
            "gradeCode": self.grade_code,
            "courseTypeCode[]": course_list,
            "classorgIdList[]": classorg_list,
            "schoolId": self.school_id,
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

    def get_basicinfo(self, exampaper_id):
        """
        获取考试中考试信息
        :param exampaper_id:考试examid
        :return: exampaper的json信息
        """

        url = f"{self.base_url}/api/examcenter/teacher/exam/basicinfo?exampaperId={exampaper_id}"

        try:
            response = requests.get(url, headers=self.headers)

            if response.status_code == 200:
                data = json.loads(response.content)
                exampaper_info = data['data']
                return exampaper_info
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

        except json.JSONDecodeError as e:
            logging.error("JSON 解析错误：%s", str(e))
            raise Exception(f"JSON 解析错误：{str(e)}")

    def login_to_school(self, **kwargs):
        self.base_envi = kwargs.get('base_envi', "xqdsj")
        self.school_id = kwargs.get('school_id')

        username = kwargs.get('username', "13951078683@xuece")
        password = kwargs.get('password', "c50d98c79dbdb8049ab1571444771e68")

        self._update_headers()
        self.configure_logging()

        self.login_and_get_auth_token(username, password)
        self.switch_school()

    def get_classorg_list(self):
        url = f"{self.base_url}/api/usercenter/teacher/classorg/listbygrade?schoolId={self.school_id}&gradeCode={self.grade_code}"

        try:
            response = requests.get(url, headers=self.headers)

            if response.status_code == 200:
                data = json.loads(response.content)
                # data = json.dumps(data, indent=4, ensure_ascii=False)
                data = data.get('data')
                classorg_list = []
                for i in data:
                    classorg_list.append(i['id'])
                return classorg_list
            else:
                logging.error("请求失败，状态码为：%d", response.status_code)
                raise Exception(f"请求失败，状态码为：{response.status_code}")
        except requests.exceptions.RequestException as e:
            logging.error("请求异常：%s", str(e))
            raise Exception(f"请求异常：{str(e)}")

    def copy_ai_marking(self, **kwargs):
        """
        复制智能阅卷设置
        考试设置得为空
        TODO：后期添加清空智能阅卷设置，后再进行复制
        """
        examination_id = kwargs.get('examination_id', 22011)

        # 生产拿去考试信息 examination_id =21365
        self.login_to_school(base_envi="xqdsj.xuece.cn", school_id=7, username="13951078683@xuece",
                             password="c50d98c79dbdb8049ab1571444771e68")

        data = self.get_answercard_detail(examination_id)
        datalist = self.extract_data(data)

        exampaper_data = datalist[1]
        exampaper_id = exampaper_data['id']

        # 获取考试的智能批阅设置
        ai_marking_info = self.get_ai_marking_info(exampaper_id)

        # test1环境复制设置
        self.login_to_school(base_envi="xuece-xqdsj-stagingtest1.unisolution.cn", school_id=2,
                             username="testOp01",
                             password="c50d98c79dbdb8049ab1571444771e68")

        # 获取英语考试id
        examination_id_new = kwargs.get('examination_id_new', 10121)
        data = self.get_answercard_detail(examination_id_new)
        datalist = self.extract_data(data)

        exampaper_data = datalist[1]
        exampaper_id = exampaper_data['id']

        ai_marking_info_list = self.excute_marking_info(exampaper_id, ai_marking_info)

        # 设置智能批阅阅卷设置
        if not ai_marking_info_list:
            logging.info("原试卷未设置智能批阅阅卷设置")
        else:
            for data in ai_marking_info_list:
                self.save_ai_marking_info(data)

        logging.info("复制智能阅卷设置成功")

    def copy_exam(self, **kwargs):
        """
        复制考试
        """
        # examinationId = input("请输入考试 examinationId ")
        # examination_id = 21507
        examination_id = kwargs.get('examination_id', 22011)
        school_id = kwargs.get('school_id', self.target_school_id)

        # 生产拿去考试信息 examination_id =21365
        self.login_to_school(base_envi="xqdsj.xuece.cn", school_id=7, username="13951078683@xuece",
                             password="c50d98c79dbdb8049ab1571444771e68")

        data = self.get_answercard_detail(examination_id)
        datalist = self.extract_data(data)

        answercard_data = datalist[0]
        exampaper_data = datalist[1]
        exampaper_id = exampaper_data['id']
        exam_name = exampaper_data['title']

        # 获取考试的智能批阅设置
        ai_marking_info = self.get_ai_marking_info(exampaper_id)

        # test1环境复制设置
        self.login_to_school(base_envi="xuece-xqdsj-stagingtest1.unisolution.cn", school_id=school_id,
                             username="testOp01",
                             password="c50d98c79dbdb8049ab1571444771e68")

        examination_id = self.examin_create(exam_name)

        exam_info = self.get_examinfo(examination_id)
        exampaper_list = exam_info['exampapers']

        for exampaper in exampaper_list:
            if exampaper['courseCode'] == self.exam_course:
                exampaper_id = exampaper['id']
        self.create_manually(exampaper_id)

        self.update_structureseq(exampaper_data, exampaper_id)
        self.save_editinfo(answercard_data, exampaper_id)

        # 获取新考试答题卡id
        data = self.get_answercard_detail(examination_id)
        datalist = self.extract_data(data)
        answercard_data = datalist[0]

        answercard_id = answercard_data['id']
        # 发布答题卡
        time.sleep(5)
        self.publish_answercard(answercard_id)

        ai_marking_info_list = self.excute_marking_info(exampaper_id, ai_marking_info)

        # 设置智能批阅阅卷设置
        if not ai_marking_info_list:
            logging.info("原试卷未设置智能批阅阅卷设置")
        else:
            for data in ai_marking_info_list:
                self.save_ai_marking_info(data)

        logging.info("复制成功")
        logging.info(
            f"考试地址：https://xuece-xqdsj-stagingtest1.unisolution.cn/editor/editAnswerTable"
            f"?examinationId={examination_id}&step=2&isIntelligence=2"
        )

    def copy_all_exam(self, **kwargs):
        """
        复制完整的考试
        """
        # examinationId = input("请输入考试 examinationId ")
        # examination_id = 21507
        examination_id = kwargs.get('examination_id', 22011)
        school_id = kwargs.get('school_id', self.target_school_id)

        # 生产拿去考试信息
        self.login_to_school(base_envi="xqdsj.xuece.cn", school_id=7, username="13951078683@xuece",
                             password="c50d98c79dbdb8049ab1571444771e68")

        examination_data = self.get_answercard_detail(examination_id)
        exam_course_list = self.extract_exam_course_list(examination_data)

        datalist = self.extract_data(examination_data, exam_course=exam_course_list[0])
        exampaper_data = datalist[1]
        exam_name = exampaper_data['title']
        # test1环境复制设置
        self.login_to_school(base_envi="xuece-xqdsj-stagingtest1.unisolution.cn", school_id=school_id,
                             username="testOp01",
                             password="c50d98c79dbdb8049ab1571444771e68")
        examination_id = self.examin_create(exam_name, exam_course_list=exam_course_list)
        exam_info = self.get_examinfo(examination_id)
        exampaper_list = exam_info['exampapers']

        for course in exam_course_list:

            datalist = self.extract_data(examination_data, exam_course=course)

            answercard_data = datalist[0]
            exampaper_data = datalist[1]
            exampaper_id = exampaper_data['id']

            # 生产拿去考试信息
            self.login_to_school(base_envi="xqdsj.xuece.cn", school_id=7, username="13951078683@xuece",
                                 password="c50d98c79dbdb8049ab1571444771e68")
            # 获取考试的智能批阅设置
            ai_marking_info = self.get_ai_marking_info(exampaper_id)

            # test1环境复制设置
            self.login_to_school(base_envi="xuece-xqdsj-stagingtest1.unisolution.cn", school_id=school_id,
                                 username="testOp01",
                                 password="c50d98c79dbdb8049ab1571444771e68")

            for exampaper in exampaper_list:
                if exampaper['courseCode'] == course:
                    exampaper_id = exampaper['id']
            self.create_manually(exampaper_id)

            self.update_structureseq(exampaper_data, exampaper_id)
            self.save_editinfo(answercard_data, exampaper_id)

            # 获取新考试答题卡id
            data = self.get_answercard_detail(examination_id)
            datalist = self.extract_data(data, exam_course=course)
            answercard_data = datalist[0]

            answercard_id = answercard_data['id']
            # 发布答题卡
            time.sleep(2)
            self.publish_answercard(answercard_id)

            ai_marking_info_list = self.excute_marking_info(exampaper_id, ai_marking_info)

            # 设置智能批阅阅卷设置
            if not ai_marking_info_list:
                logging.info("原试卷未设置智能批阅阅卷设置")
            else:
                for data in ai_marking_info_list:
                    self.save_ai_marking_info(data)

            logging.info("复制成功")
            logging.info(
                f"考试地址：https://xuece-xqdsj-stagingtest1.unisolution.cn/editor/editAnswerTable"
                f"?examinationId={examination_id}&step=2&isIntelligence=2"
            )


if __name__ == "__main__":
    api = ApiRequest(target_school_id=63, grade_code="S03", exam_course="ENGLISH")
    # api.copy_exam(examination_id=28681)
    api.copy_all_exam(examination_id=20108)
