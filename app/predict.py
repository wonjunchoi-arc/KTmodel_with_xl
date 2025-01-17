import os
import sys
current_directory = os.path.dirname(os.path.abspath(__file__))
parent_directory = os.path.dirname(current_directory)
sys.path.append(parent_directory)
from fastapi import HTTPException
import pandas as pd
import tensorflow as tf
from preprocess.data_utils import get_evalmask_token
from models.model_for_kt import TFTransfoXLMLMHeadModel
from pathlib import Path
from transformers import TransfoXLConfig
import argparse


__version__="0.1.0"
BASE_DIR = Path(__file__).resolve(strict=True).parent.parent

def predict_pipline(path,uid,devices):

    device = "/cpu:0" if device == "cpu" else "/gpu:0"
    try:
        with tf.device(device):

            config_xl = TransfoXLConfig.from_pretrained('{}/save_model/5ep_400mem_concepts.ckpt/config.json'.format(BASE_DIR))

            model = TFTransfoXLMLMHeadModel(config=config_xl)
            model.load_weights('{}/save_model/5ep_400mem_concepts.ckpt/my_checkpoint'.format(BASE_DIR))

            csv_file_path = path # 이 값을 사용자가 넣을 수 있도록 하자

            df= pd.read_csv(csv_file_path)

            question_list = df.loc[df['uid'] == uid, 'questions']
            concepts_list = df.loc[df['uid'] == uid, 'concepts']
            responses_list = df.loc[df['uid'] == uid, 'responses']

            question_list = [int(x) for x in question_list.values[0].split(',')]
            concepts_list = [int(x) for x in concepts_list.values[0].split(',')]
            responses_list = [int(x) for x in responses_list.values[0].split(',')]

            masked_R, labels = get_evalmask_token(responses_list,config_xl.mask_token, config_xl.eos_token)



            # 여기서 읽어온 데이터를 딕셔너리키 가지고 변환해서 ip mapping 하고 


            new_shape = (-1, 1)  # 나머지 차원은 자동으로 계산됨

            qseq_reshaped = tf.reshape(question_list, new_shape)
            cseq_reshaped = tf.reshape(concepts_list, new_shape)
            masked_R_reshaped = tf.reshape(masked_R, new_shape)
            labels_reshaped = tf.reshape(labels, new_shape)
            

            # qseq_transposed = tf.transpose(qseq_reshaped)
            # cseq_transposed = tf.transpose(cseq_reshaped)
            # masked_R_transposed = tf.transpose(masked_R_reshaped)
            # labels_transposed = tf.transpose(labels_reshaped)

            

            if config_xl.mode == 'concepts':
                predict_dataset = tf.data.Dataset.from_tensor_slices(
                (cseq_reshaped, masked_R_reshaped,labels_reshaped))
            else:
                predict_dataset = tf.data.Dataset.from_tensor_slices(
                (qseq_reshaped, masked_R_reshaped,labels_reshaped))

            predict_dataset =predict_dataset.batch(config_xl.tgt_len)
            # predict_dataset =predict_dataset.batch(140)

            mems =None
            predictions = []
            for input_data, input_data2, input_target in predict_dataset:
            
                    outputs = model(concepts=tf.transpose(input_data), responses=tf.transpose(input_data2), labels=tf.transpose(input_target), mems=mems)
                    logit = outputs.logit
                    mems = outputs.mems
                    
                    reshape = tf.reshape(logit, [-1, config_xl.R_vocab_size])
                    predicted_labels = tf.argmax(reshape, axis=1)
                    predictions.append(predicted_labels.numpy().tolist())

            flattened_list = [item for sublist in predictions for item in sublist]

            df = pd.DataFrame({'Question':question_list,'Concepts':concepts_list,'Responses':flattened_list})
            save_dir = '{}/{}.csv'.format(BASE_DIR, uid)

            df.to_csv(save_dir, index=False)
        return save_dir

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
