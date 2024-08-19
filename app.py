import gradio as gr
# import PyMuPDF
import fitz
from openai import OpenAI
import re

# Solar LLM 클라이언트 초기화

client = OpenAI(api_key="up_L4wu6Az9MjVfUQH7FLEUwozfvfJZa", base_url="https://api.upstage.ai/v1/solar")

def postprocess_summary(text):
    # "이 섹션에서는"과 "이 섹션은","이 자료는"으로 시작하는 문장 제거
    pattern = re.compile(r'이 (섹션(?:에서는|은)|자료는) [^\.]*\.')
    # 제거된 텍스트 반환
    postprocessed_text = re.sub(pattern, '', text)
    return postprocessed_text.strip()

# Function to extract highlighted text from PDF
def extract_highlighted_text(pdf):
    doc = fitz.open(pdf)
    all_highlights = ""
    for page in doc:
        for annot in page.annots():
            if annot.type[0] == 8:  # 8 represents highlight annotation
                rect = annot.rect
                words = page.get_text("words")
                highlight_text = ""
                for w in words:
                    if fitz.Rect(w[:4]).intersects(rect):
                        highlight_text += w[4] + " "
                all_highlights += highlight_text.strip() + "\n"
    return all_highlights

# Function to extract specific sections (e.g., R&D, IP updates, employee status)
def extract_information(pdf):
    doc = fitz.open(pdf.name)
    all_text = ""
    for page in doc:
        all_text += page.get_text()

    extract_dict = {
        '연구현황': '',
        '특허현황': '',
        '총 인력': '',
        '성장성': ''
    }

    # Extract Current state of research information
    start_phrase = "라. 연구개발실적"
    end_phrase = "마. 정부과제 수행실적"
    start_index = all_text.find(start_phrase)
    end_index = all_text.find(end_phrase)
    if start_index != -1 and end_index != -1:
        extracted_text = all_text[start_index:end_index]
        extract_dict['연구현황'] =extracted_text

    # Extract R&D and Employee Information
    start_phrase = "(2) 연구개발인력 현황"
    end_phrase = "(3) 주요"
    start_index = all_text.find(start_phrase)
    end_index = all_text.find(end_phrase)
    if start_index != -1 and end_index != -1:
        target_sentence = all_text[start_index+1:end_index]
        # number = ''.join(filter(str.isdigit, target_sentence))
        # extract_dict['총 인력'] = f'{number}명'
        extract_dict['총 인력'] =target_sentence

    # Extract Growth Information
    start_phrase_growth = "마. 시장의 주요 특성ㆍ규모 및 성장성"
    end_phrase_growth = ")규모입니다."
    start_index_growth = all_text.find(start_phrase_growth)
    end_index_growth = all_text.find(end_phrase_growth)
    if start_index_growth != -1 and end_index_growth != -1:
        extracted_text = all_text[start_index_growth+1:end_index_growth + len(end_phrase_growth)]
        extract_dict['성장성'] = extracted_text

    # Extract IP Section: Title and One-Sentence Description
    ip_start_phrase = "3) 중공 Silica 제조 및 응용기술 관련 등록특허"
    ip_end_phrase = "4) 중공 Silica 관련 당사 보유 핵심 기술"  # Example end phrase
    ip_start_index = all_text.find(ip_start_phrase)
    ip_end_index = all_text.find(ip_end_phrase)

    if ip_start_index != -1 and ip_end_index != -1:
        # ip_content = all_text[ip_start_index:ip_end_index].strip().split("\n")[0]  # Take the first sentence after the title
        # extract_dict['특허현황'] = f"**IP Section**: {ip_content}"
        extracted_text = all_text[ip_start_index:ip_end_index]
        extract_dict['특허현황'] =extracted_text

    return extract_dict

# Function to summarize the input using Solar LLM
def summarize_text(text, detail_level='short'):
    # Adjust the prompt and call to OpenAI's Solar LLM
    prompt_content = '이 섹션을 요약해주세요.' if detail_level == 'detailed' else '이 섹션을 간략하게 요약해주세요.'

    stream = client.chat.completions.create(
        model="solar-1-mini-chat",
        messages=[
            {"role": "system", "content":prompt_content},
            {"role": "user", "content": text}
        ],
        stream=True,
        temperature=0.3
    )

    summary = ""
    for chunk in stream:
        if chunk.choices[0].delta.content is not None:
            summary += chunk.choices[0].delta.content

    summary=postprocess_summary(summary)
    return summary

import gradio as gr

# Function to handle chatbot messages
def chatbot(messages, file=None, user_question=None):
    if not messages:
        messages = [["assistant", "Hello, please upload your business report (pdf)."]]
    if file:
        highlighted_text = extract_highlighted_text(file)  # 파일에서 중요한 텍스트 추출
        extracted_info = extract_information(file)  # 파일에서 정보 추출
        combined_info = f"Highlights:\n{highlighted_text}\n\nDetails:\n{extracted_info}"
        detailed_summary = summarize_text(combined_info).replace('\n', '\n- ')
        short_insight = summarize_text(combined_info).replace('\n', '\n- ')
        summarized_output = f"**Company Overview:**\n{detailed_summary}\n\n**Detailed Insights:**\n{short_insight}"
        messages.append(["user", "Please analyze this report"])
        messages.append(["assistant", summarized_output])
        return messages  # 파일 업로드 후 메시지 리스트 반환
    if user_question:
        answer = generate_answer(user_question)
        messages.append(["user", user_question])
        messages.append(["assistant", answer])
    return messages  # 사용자 질문에 대한 응답 후 메시지 반환

def generate_answer(question):
    response = client.chat.completions.create(
        model="solar-1-mini-chat",
        messages=[
            {"role": "system", "content": "Here are recent updates."},
            {"role": "user", "content": question}
        ],
        temperature=0.1
    )
    answer = response.choices[0].message.content
    return answer

with gr.Blocks() as demo:
    chatbot_widget = gr.Chatbot(label="chatbot", height=400)
    user_question_input = gr.Textbox(interactive=True, placeholder="Type your questions here...")
    file_upload = gr.File(label="Upload business reports here (PDF)", type="filepath")  # type 수정
    submit_btn = gr.Button("Submit")
    clear_btn = gr.ClearButton([chatbot_widget, user_question_input])  # 초기화 버튼

    def on_submit(file, history, user_question):
        # 파일 데이터가 제공된 경우, 파일 경로를 사용하여 처리
        if file:
            return chatbot(history, file, user_question)
        return chatbot(history, None, user_question)  # 파일이 없으면 None 전달
    def initial_greeting():
        return chatbot([])
    demo.load(initial_greeting, outputs=chatbot_widget)
    file_upload.change(on_submit, [file_upload, chatbot_widget, user_question_input], [chatbot_widget])
    submit_btn.click(on_submit, [file_upload, chatbot_widget, user_question_input], [chatbot_widget])
    user_question_input.submit(on_submit, [file_upload, chatbot_widget, user_question_input], [chatbot_widget])
    with gr.Row():
        gr.Column([chatbot_widget, user_question_input, file_upload, submit_btn, clear_btn])
# Gradio 애플리케이션 실행
demo.launch(debug=True)

