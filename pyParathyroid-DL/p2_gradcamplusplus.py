
# -*- coding: utf-8 -*-
"""
@author: lisssse14
"""
import tensorflow as tf
from tesnorflow.keras import backend as K
from tesnorflow.keras.applications.resnet50 import ResNet50
from tesnorflow.keras.applications.imagenet_utils import preprocess_input, decode_predictions
from tesnorflow.keras.preprocessing.image import img_to_array, load_img, array_to_img
import numpy as np
import cv2
import os
# 自動增加 GPU 記憶體用量
config = tf.ConfigProto()
config.gpu_options.allow_growth=True
sess = tf.Session(config=config)
# 設定 Keras 使用的 Session
K.set_session(sess)
K.set_learning_phase(1)


def preprocess_image(image, pre_process=True):
    #x = img_to_array(image)
    x = np.expand_dims(image, axis=0)
    if pre_process:
        x = preprocess_input(x)
    return x

class gradient_cams(object):
    def __init__(self, model, target_layer):
        self.model = model
        self.target_layer = target_layer
     
    def grad_cam(self, image):
        img = preprocess_image(image)
        prediction = model.predict(img)
        pred_class = np.argmax(prediction[0])
        #pred_class_name = decode_predictions(prediction)[0][0][1]
        pred_output = model.output[:, pred_class]
        last_conv_output = model.get_layer(target_layer).output
        #梯度公式
        grads = K.gradients(pred_output, last_conv_output)[0]
        #定義計算函數
        gradient_function = K.function([model.input], [last_conv_output, grads])
        output, grads_val = gradient_function([img])
        output, grads_val = output[0], grads_val[0]
        # 取得所有梯度的平均值
        weights = np.mean(grads_val, axis=(0, 1))
        gradcam = np.dot(output, weights)
        #梯度RGB化
        gradcam = cv2.resize(gradcam, (224,224), cv2.INTER_LINEAR)
        gradcam = np.maximum(gradcam, 0)
        heatmap = gradcam / gradcam.max()
        # 上色
        jetcam = cv2.applyColorMap(np.uint8(255 * heatmap), cv2.COLORMAP_JET)
        jetcam = (np.float32(jetcam) + image / 2)
        return jetcam

    
    def grad_cam_plus_plus(self, image):
        img = preprocess_image(image, pre_process=False)
        img = img /255.0
        # 取得預測類別
        predictions = model.predict(img)
        class_idx = np.argmax(predictions[0])
        # 取得權重，供計算導數
        class_output = model.layers[-1].output
        conv_output = model.get_layer(target_layer).output
        grads = K.gradients(class_output, conv_output)[0]
        # 一階微分
        first_derivative = K.exp(class_output)[0][class_idx] * grads
        # 二階微分
        second_derivative = K.exp(class_output)[0][class_idx] * grads * grads
        # 三階微分
        third_derivative = K.exp(class_output)[0][class_idx] * grads * grads * grads
        # function 定義 輸出conv_output和grads的函數
        gradient_function = K.function([model.input], [conv_output, first_derivative, second_derivative,
                                                       third_derivative])

        conv_output, conv_first_grad, conv_second_grad, conv_third_grad = gradient_function([img])
        conv_output, conv_first_grad, conv_second_grad, conv_third_grad = conv_output[0], conv_first_grad[0], \
                                                                          conv_second_grad[0], conv_third_grad[0]

        # alpha取得
        global_sum = np.sum(conv_output.reshape((-1, conv_first_grad.shape[2])), axis=0)
        alpha_num = conv_second_grad
        alpha_denom = conv_second_grad * 2.0 + conv_third_grad * global_sum.reshape((1, 1, conv_first_grad.shape[2]))
        alpha_denom = np.where(alpha_denom != 0.0, alpha_denom, np.ones(alpha_denom.shape))
        alphas = alpha_num / alpha_denom
        # alpha 正規化
        alpha_normalization_constant = np.sum(np.sum(alphas, axis=0), axis=0)
        alpha_normalization_constant_processed = np.where(alpha_normalization_constant != 0.0,
                                                          alpha_normalization_constant,
                                                          np.ones(alpha_normalization_constant.shape))
        alphas /= alpha_normalization_constant_processed.reshape((1, 1, conv_first_grad.shape[2]))
        #  Weight 計算
        weights = np.maximum(conv_first_grad, 0.0)
        deep_linearization_weights = np.sum((weights * alphas).reshape((-1, conv_first_grad.shape[2])))
        # L 計算
        grad_CAM_map = np.sum(deep_linearization_weights * conv_output, axis=2)
        grad_CAM_map = np.maximum(grad_CAM_map, 0)
        grad_CAM_map = grad_CAM_map / np.max(grad_CAM_map)
        # 繪製熱力圖
        grad_CAM_map = cv2.resize(grad_CAM_map, (224, 224), cv2.INTER_LINEAR)
        jetcam = cv2.applyColorMap(np.uint8(255 * grad_CAM_map), cv2.COLORMAP_JET)
        # 與原影像疊加
        jetcam = (np.float32(jetcam) + image / 2)

        return jetcam


# if __name__ == '__main__':
#     model = ResNet50(weights='imagenet')
#     image_path = 'boat.jpg'
#     target_height, target_width = (224,224)
#     image = load_img(image_path)
#     #original_height, original_width = (image.height, image.width)
#     image = image.resize((target_height,target_width),3)
#     image = img_to_array(image)
#     target_layer = 'activation_49'
#     vis = gradient_cams(model, target_layer)
# # =============================================================================
# #     grad_cam
# # =============================================================================
#     grad = vis.grad_cam(image)
#     cv2.imwrite(os.path.splitext(image_path)[0]+'_gcam.jpg', grad)
# # =============================================================================
# #     grad_cam++
# # =============================================================================
#     grad_plus = vis.grad_cam_plus_plus(image)
#     cv2.imwrite(os.path.splitext(image_path)[0]+'gcam++.jpg', grad_plus)