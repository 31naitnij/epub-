from openai import OpenAI
import json

class Translator:
    def __init__(self, api_key, base_url, model, temperature, system_prompt):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.temperature = float(temperature)
        self.system_prompt = system_prompt

    def translate_chunk(self, current_text, prev_orig=None, prev_trans=None):
        messages = [
            {"role": "system", "content": self.system_prompt}
        ]
        
        # Standard multi-turn dialogue context
        if prev_orig and prev_trans:
            messages.append({"role": "user", "content": prev_orig})
            messages.append({"role": "assistant", "content": prev_trans})
            
        messages.append({"role": "user", "content": current_text})
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                stream=True
            )
            for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            print(f"翻译出错: {e}")
            yield f"[翻译错误: {e}]"
