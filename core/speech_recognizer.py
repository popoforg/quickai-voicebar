import pyaudio
import numpy as np
import threading
import os
import re
import time
import wave
import tempfile

# 设置 ONNX Runtime 多线程并行推理（与 Vocotype 一致）
os.environ.setdefault("OMP_NUM_THREADS", "8")

class SpeechRecognizer:
    MIN_RECORD_SECONDS = 0.25
    MIN_SPEECH_RMS = 280

    def __init__(self, text_update_callback):
        self.text_update_callback = text_update_callback
        self.is_listening = False
        self.listen_thread = None
        self.audio_buffer = []
        
        self.p = pyaudio.PyAudio()
        self.sample_rate = 16000
        self.channels = 1
        self.format = pyaudio.paInt16
        self.chunk_size = 1600  # 0.1s
        
        self.asr_model = None
        self.punc_model = None
        self._init_model_thread = threading.Thread(target=self._init_model_async, daemon=True)
        self._init_model_thread.start()

    def _init_model_async(self):
        """后台加载 ONNX 模型（仅从本地缓存加载，下载由弹窗完成）"""
        print("正在初始化 ONNX 语音引擎...")
        start_time = time.time()
        
        try:
            # === 模型目录（由 model_downloader_dialog 提前下载好） ===
            asr_model_dir = os.path.expanduser(
                "~/.cache/modelscope/hub/models/iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-onnx"
            )
            punc_model_dir = os.path.expanduser(
                "~/.cache/modelscope/hub/models/iic/punc_ct-transformer_zh-cn-common-vocab272727-onnx"
            )
            
            # === 加载 ASR 模型 (Paraformer ONNX) ===
            from funasr_onnx.paraformer_bin import Paraformer
            num_threads = int(os.environ.get("OMP_NUM_THREADS", "8"))
            
            quant_file = os.path.join(asr_model_dir, "model_quant.onnx")
            use_quantize = os.path.exists(quant_file)
            
            self.asr_model = Paraformer(
                str(asr_model_dir),
                batch_size=1,
                device_id=-1,
                quantize=use_quantize,
                intra_op_num_threads=num_threads,
            )
            print(f"  ASR 模型加载完成 (量化={use_quantize}, 线程={num_threads})")
            
            # === 加载标点恢复模型 (CT_Transformer ONNX) ===
            from funasr_onnx.punc_bin import CT_Transformer
            punc_quant = os.path.exists(os.path.join(punc_model_dir, "model_quant.onnx"))
            
            self.punc_model = CT_Transformer(
                str(punc_model_dir),
                batch_size=1,
                device_id=-1,
                quantize=punc_quant,
                intra_op_num_threads=num_threads,
            )
            print(f"  标点模型加载完成 (量化={punc_quant})")
            
            # === 预热 librosa（与 Vocotype 一致，避免首次 load 延迟） ===
            try:
                import librosa
                fd, tmp_path = tempfile.mkstemp(suffix='.wav')
                os.close(fd)
                with wave.open(tmp_path, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(16000)
                    wf.writeframes(np.zeros(1600, dtype=np.int16).tobytes())
                librosa.load(tmp_path, sr=16000)
                os.remove(tmp_path)
                print("  librosa 预热完成")
            except Exception:
                pass
            
            # === 预热 ASR 模型（首次推理触发 ONNX Session 初始化） ===
            try:
                fd, tmp_path = tempfile.mkstemp(suffix='.wav')
                os.close(fd)
                with wave.open(tmp_path, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(16000)
                    wf.writeframes(np.zeros(16000, dtype=np.int16).tobytes())  # 1秒静音
                self.asr_model([tmp_path])
                os.remove(tmp_path)
                print("  ASR 推理预热完成")
            except Exception:
                pass
            
            elapsed = time.time() - start_time
            print(f"🚀 ONNX 语音引擎全部就绪！总耗时 {elapsed:.1f}s，极速 Push-To-Talk 模式已激活。")
            
        except Exception as e:
            print(f"ONNX 语音引擎初始化失败: {e}")
            import traceback
            traceback.print_exc()

    def start_listening(self):
        """按下按键时触发，直接开始无脑写入缓存"""
        if self.is_listening:
            return

        self.is_listening = True
        self.audio_buffer = []
        
        self.listen_thread = threading.Thread(target=self._record_loop, daemon=True)
        self.listen_thread.start()

    def stop_and_recognize(self):
        """松开按键时触发：即刻停止，提取整段录音送去 ONNX 一次性辨认"""
        self.is_listening = False
        
        # 立即剪断取件，绝不阻塞
        buffer_copy = list(self.audio_buffer)
        self.audio_buffer = []
        
        if not self.asr_model or not buffer_copy:
            return

        full_data = b''.join(buffer_copy)
        if not self._should_recognize_audio(full_data):
            return

        # 交给后台线程进行 ONNX 推理，绝对不阻塞 UI
        threading.Thread(target=self._recognize_async, args=(full_data,), daemon=True).start()
            
    def _recognize_async(self, full_data):
        """后台执行 ONNX 推理（与 Vocotype 完全一致：写临时 WAV → ONNX 推理 → 标点恢复）"""
        start = time.time()
        recognized_text = ""
        
        # 写入临时 WAV 文件（funasr_onnx 的接口要求）
        fd, tmp_path = tempfile.mkstemp(suffix='.wav')
        os.close(fd)
        try:
            with wave.open(tmp_path, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                wf.writeframes(full_data)
            
            # ONNX 推理
            asr_result = self.asr_model([tmp_path])
            
            if isinstance(asr_result, list) and len(asr_result) > 0:
                first_item = asr_result[0]
                if isinstance(first_item, dict) and "preds" in first_item:
                    preds = first_item["preds"]
                    raw_text = str(preds[0]) if isinstance(preds, tuple) else str(preds)
                elif isinstance(first_item, dict) and "text" in first_item:
                    raw_text = first_item["text"]
                else:
                    raw_text = str(first_item)
            else:
                raw_text = str(asr_result)
            
            # 过滤标签
            raw_text = re.sub(r'<[^>]+>', '', raw_text).strip()
            
            # 标点恢复
            if self.punc_model and raw_text:
                try:
                    punc_result = self.punc_model(raw_text)
                    if isinstance(punc_result, tuple) and len(punc_result) > 0:
                        recognized_text = str(punc_result[0])
                    else:
                        recognized_text = str(punc_result)
                except Exception:
                    recognized_text = raw_text
            else:
                recognized_text = raw_text
                
        except Exception as e:
            print(f"ONNX 推理发生错误：{e}")
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        
        elapsed = time.time() - start
        print(f"⚡ ONNX 推理完成: {elapsed:.3f}s → \"{recognized_text[:50]}\"")
        
        # 后处理：应用配置中的文本清理规则
        if recognized_text:
            recognized_text = self._post_process(recognized_text)
        
        # 抛给 UI
        if recognized_text:
            self.text_update_callback(recognized_text)

    def _post_process(self, text):
        """根据 config 中的设置对识别结果进行后处理"""
        import config as cfg
        
        # 删除结尾句号
        if getattr(cfg, 'STRIP_TRAILING_PERIOD', False):
            text = text.rstrip('。.')
        
        # 过滤语气词
        if getattr(cfg, 'FILTER_FILLER_WORDS', False):
            filler_words = ['嗯', '啊', '呃', '额', '哦', '噢', '呢', '吧', '哈', '唔', '嘛']
            filler_pattern = "|".join(map(re.escape, filler_words))
            # 删除语气词，以及其后紧跟的中英文逗号和多余空白
            text = re.sub(rf'(?<!\S)(?:{filler_pattern})(?:\s*[，,])?(?!\S)', ' ', text)
            text = re.sub(rf'^(?:{filler_pattern})(?:\s*[，,])?\s*', '', text)
            text = re.sub(rf'\s*(?:{filler_pattern})(?:\s*[，,])?', '', text)
            # 清理多余空格和残留逗号间距
            text = re.sub(r'\s+', ' ', text).strip()
            text = re.sub(r'\s*([，,])\s*', r'\1', text)
        
        return text

    def _should_recognize_audio(self, full_data):
        """过滤误触、静音和极低音量音频，避免空白录音生成垃圾文本"""
        sample_count = len(full_data) // 2
        if sample_count <= 0:
            return False

        duration_seconds = sample_count / self.sample_rate
        if duration_seconds < self.MIN_RECORD_SECONDS:
            return False

        samples = np.frombuffer(full_data, dtype=np.int16)
        if samples.size == 0:
            return False

        rms = float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))
        if rms < self.MIN_SPEECH_RMS:
            print(f"跳过静音/误触音频: duration={duration_seconds:.3f}s, rms={rms:.1f}")
            return False

        return True

    def stop_listening(self):
        """强制取消、不识别的强退接口（例如按下ESC）"""
        self.is_listening = False

    def _record_loop(self):
        """极致轻量的录音线程，无推理负载"""
        try:
            stream = self.p.open(format=self.format,
                                 channels=self.channels,
                                 rate=self.sample_rate,
                                 input=True,
                                 frames_per_buffer=self.chunk_size)
        except Exception as e:
            print(f"打开麦克风失败: {e}")
            self.is_listening = False
            return
            
        while self.is_listening:
            try:
                data = stream.read(self.chunk_size, exception_on_overflow=False)
                self.audio_buffer.append(data)
            except Exception:
                break
                
        stream.stop_stream()
        stream.close()
