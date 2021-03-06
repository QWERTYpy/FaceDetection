import numpy as np
import sys
import cv2
import os


os.environ['KERAS_BACKEND'] = 'tensorflow'

from keras.models import load_model



def interpret_output_yolov2(output, img_width, img_height):
	anchors = [0.57273, 0.677385, 1.87446, 2.06253, 3.33843, 5.47434, 7.88282, 3.52778, 9.77052, 9.16828]

	netout = output
	nb_class = 1
	obj_threshold = 0.4
	nms_threshold = 0.3

	grid_h, grid_w, nb_box = netout.shape[:3]

	size = 4 + nb_class + 1;
	nb_box = 5

	netout = netout.reshape(grid_h, grid_w, nb_box, size)

	boxes = []

	# decode the output by the network
	netout[..., 4] = _sigmoid(netout[..., 4])
	netout[..., 5:] = netout[..., 4][..., np.newaxis] * _softmax(netout[..., 5:])
	netout[..., 5:] *= netout[..., 5:] > obj_threshold

	for row in range(grid_h):
		for col in range(grid_w):
			for b in range(nb_box):
				# from 4th element onwards are confidence and class classes
				classes = netout[row, col, b, 5:]

				if np.sum(classes) > 0:
					# first 4 elements are x, y, w, and h
					x, y, w, h = netout[row, col, b, :4]

					x = (col + _sigmoid(x)) / grid_w  # center position, unit: image width
					y = (row + _sigmoid(y)) / grid_h  # center position, unit: image height
					w = anchors[2 * b + 0] * np.exp(w) / grid_w  # unit: image width
					h = anchors[2 * b + 1] * np.exp(h) / grid_h  # unit: image height
					confidence = netout[row, col, b, 4]

					box = bounding_box(x - w / 2, y - h / 2, x + w / 2, y + h / 2, confidence, classes)

					boxes.append(box)

	# suppress non-maximal boxes
	for c in range(nb_class):
		sorted_indices = list(reversed(np.argsort([box.classes[c] for box in boxes])))

		for i in range(len(sorted_indices)):
			index_i = sorted_indices[i]

			if boxes[index_i].classes[c] == 0:
				continue
			else:
				for j in range(i + 1, len(sorted_indices)):
					index_j = sorted_indices[j]

					if bbox_iou(boxes[index_i], boxes[index_j]) >= nms_threshold:
						boxes[index_j].classes[c] = 0

	# remove the boxes which are less likely than a obj_threshold
	boxes = [box for box in boxes if box.get_score() > obj_threshold]

	result = []
	for i in range(len(boxes)):
		if (boxes[i].classes[0] == 0):
			continue
		predicted_class = "face"
		score = boxes[i].score
		result.append([predicted_class, (boxes[i].xmax + boxes[i].xmin) * img_width / 2,
					   (boxes[i].ymax + boxes[i].ymin) * img_height / 2, (boxes[i].xmax - boxes[i].xmin) * img_width,
					   (boxes[i].ymax - boxes[i].ymin) * img_height, score])

	return result


class bounding_box:
	def __init__(self, xmin, ymin, xmax, ymax, c=None, classes=None):
		self.xmin = xmin
		self.ymin = ymin
		self.xmax = xmax
		self.ymax = ymax

		self.c = c
		self.classes = classes

		self.label = -1
		self.score = -1

	def get_label(self):
		if self.label == -1:
			self.label = np.argmax(self.classes)

		return self.label

	def get_score(self):
		if self.score == -1:
			self.score = self.classes[self.get_label()]

		return self.score


def bbox_iou(box1, box2):
	intersect_w = _interval_overlap([box1.xmin, box1.xmax], [box2.xmin, box2.xmax])
	intersect_h = _interval_overlap([box1.ymin, box1.ymax], [box2.ymin, box2.ymax])

	intersect = intersect_w * intersect_h

	w1, h1 = box1.xmax - box1.xmin, box1.ymax - box1.ymin
	w2, h2 = box2.xmax - box2.xmin, box2.ymax - box2.ymin

	union = w1 * h1 + w2 * h2 - intersect

	return float(intersect) / union

def _interval_overlap(interval_a, interval_b):
	x1, x2 = interval_a
	x3, x4 = interval_b

	if x3 < x1:
		if x4 < x1:
			return 0
		else:
			return min(x2,x4) - x1
	else:
		if x2 < x3:
			 return 0
		else:
			return min(x2,x4) - x3


def _sigmoid(x):
	return 1. / (1. + np.exp(-x))


def _softmax(x, axis=-1, t=-100.):
	x = x - np.max(x)

	if np.min(x) < t:
		x = x / np.min(x) * t

	e_x = np.exp(x)

	return e_x / e_x.sum(axis, keepdims=True)


# crop
def crop(x, y, w, h, margin, img_width, img_height):
	xmin = int(x - w * margin)
	xmax = int(x + w * margin)
	ymin = int(y - h * margin)
	ymax = int(y + h * margin)
	if xmin < 0:
		xmin = 0
	if ymin < 0:
		ymin = 0
	if xmax > img_width:
		xmax = img_width
	if ymax > img_height:
		ymax = img_height
	return xmin, xmax, ymin, ymax

#display result
def show_results(img,results, img_width, img_height):
	img_cp = img.copy()
	for i in range(len(results)):
		#display detected face
		x = int(results[i][1])
		y = int(results[i][2])
		w = int(results[i][3])//2
		h = int(results[i][4])//2

		if(w<h):
			w=h
		else:
			h=w

		xmin,xmax,ymin,ymax=crop(x,y,w,h,1.0,img_width,img_height)

		cv2.rectangle(img_cp,(xmin,ymin),(xmax,ymax),(0,255,0),2)
		cv2.rectangle(img_cp,(xmin,ymin-20),(xmax,ymin),(125,125,125),-1)
		cv2.putText(img_cp,results[i][0] + ' : %.2f' % results[i][5],(xmin+5,ymin-7),cv2.FONT_HERSHEY_SIMPLEX,0.5,(0,0,0),1)

		target_image=img_cp

		#analyze detected face
		xmin2,xmax2,ymin2,ymax2=crop(x,y,w,h,1.1,img_width,img_height)

		face_image = img[ymin2:ymax2, xmin2:xmax2]

		if(face_image.shape[0]<=0 or face_image.shape[1]<=0):
			continue

		#cv2.rectangle(target_image, (xmin2,ymin2), (xmax2,ymax2), color=(0,0,255), thickness=3)


	cv2.imshow('YoloKerasFaceDetection',img_cp)

def main(argv):
	MODEL_ROOT_PATH="./pretrain/"
	# Load Model
	model_face = load_model(MODEL_ROOT_PATH + 'yolov2_tiny-face.h5')
	# Prepare WebCamera
	cap = cv2.VideoCapture(0)
	#cap = cv2.VideoCapture('rtsp://admin:admin@10.64.130.5:554/av0_1')
	cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
	cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
	name_window = 'Face'

	# Detection
	while True:
		# Face Detection
		success, image = cap.read()

		img = image
		img = img[..., ::-1]  # BGR 2 RGB
		inputs = img.copy() / 255.0
		img_cv = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
		img_camera = cv2.resize(inputs, (416, 416))
		img_camera = np.expand_dims(img_camera, axis=0)
		out2 = model_face.predict(img_camera)[0]
		results = interpret_output_yolov2(out2, img.shape[1], img.shape[0])
		show_results(img_cv, results, img.shape[1], img.shape[0])

		# cv2.namedWindow(name_window, 0)
		# cv2.imshow(name_window, image)

		if cv2.waitKey(2) == 27:  # ?????????? ???? ESC
			break
		if cv2.waitKey(1) & 0xFF == ord('q'):
			break
	cap.release()
	cv2.destroyAllWindows()

if __name__ == '__main__':
	main(sys.argv[1:])