#generate a Lut based on a gradient

import cv2
import numpy as np
import matplotlib.pyplot as plt
import json

class gradient:
    def __init__(self):
        self.colors = list()
        self.positions = list()

    def add_color(self, color, position):
        self.colors.append(color)
        self.positions.append(position)

    def get_color_at_position(self, position):
        if len(self.colors) < 2 or len(self.positions) < 2:
            exit('Error: Not enough colors defined')

        lower_bound_index = 0
        upper_bound_index = 1
        for i in range(0, len(self.positions)):
            if self.positions[i] <= position:
                lower_bound_index = i
            if self.positions[i] > position:
                upper_bound_index = i
                break

        #linear interpolation between the two colors at index lower_bound_index and upper_bound_index
        lower_bound_color = self.colors[lower_bound_index]
        upper_bound_color = self.colors[upper_bound_index]
        color_difference = np.subtract(upper_bound_color, lower_bound_color)

        lower_bound_position = self.positions[lower_bound_index]
        upper_bound_position = self.positions[upper_bound_index]
        position_difference = upper_bound_position - lower_bound_position

        position_difference_to_lower_bound = position - lower_bound_position
        if(position_difference == 0):
            color_at_position = lower_bound_color
        else:
            position_difference_to_lower_bound_relative = position_difference_to_lower_bound / position_difference
            color_at_position = np.add(lower_bound_color, np.multiply(color_difference, position_difference_to_lower_bound_relative))

        return color_at_position

    def get_lut(self, lut_size):
        lut = np.zeros((lut_size, 4), dtype=np.float)
        for i in range(0, lut_size):
            lut[i] = self.get_color_at_position(i / lut_size)
        return lut

if __name__ == '__main__':
    grad = gradient()

    # grad_numbr = 1
    # gradient_string = "rgba(0,0,0,1) 0%, rgba(255,255,255,1) 100%)"
    grad_numbr = 2
    gradient_string = "rgba(0,0,0,1) 0%, rgba(255,0,0,1) 37.5%, rgba(255,255,0,1) 75%, rgba(255,255,255,1) 100%)"
    # grad_numbr = 3
    # gradient_string = "rgba(0,0,32,1) 0%, rgba(32,0,96,1) 12.5%, rgba(181,0,164,1) 37.5%, rgba(255,64,0,1) 50%, rgba(255,255,0,1) 87.5%, rgba(255,255,200,1) 100%)"
    # grad_numbr = 4
    # gradient_string = "rgba(0,0,0,1) 0%, rgba(30,129,129,1) 35%, rgba(255,255,0,1) 75%, rgba(255,65,0,1) 93.5%, rgba(225,0,0,1) 100%)"
    # grad_numbr = 5
    # gradient_string = "rgba(0,0,0,1) 0%, rgba(221,60,221,1) 12.5%, rgba(32,32,255,1) 25%, rgba(19,240,240,1) 37.5%, rgba(0,160,0,1) 55%, rgba(224,231,14,1) 70%, rgba(255,255,19,1) 75%, rgba(255,32,32,1) 87.5%, rgba(255,255,255,1) 100%"
    # grad_numbr = 6
    # gradient_string = "rgba(0,0,0,1) 0%, rgba(0,64,255,1) 12.5%, rgba(0,160,60,1) 25%, rgba(128,255,0,1) 37.5%, rgba(255,255,0,1) 50%, rgba(255,0,0,1) 75%, rgba(255,0,255,1) 87.5%, rgba(255,255,255,1) 100%)"#6
    # grad_numbr = 7
    # gradient_string = "rgba(127,0,0,1) 0%, rgba(255,0,193,1) 12.5%, rgba(207,0,255,1) 16.5%, rgba(0,0,255,1) 33%, rgba(0,255,255,1) 50%, rgba(0,255,0,1) 66%,rgba(255,255,0,1) 82.5%, rgba(255,0,0,1) 100%)"
    # grad_numbr = 8
    # gradient_string = "rgba(0,0,128,1) 0%, rgba(0,0,255,1) 12.5%, rgba(0,255,255,1) 37.5%, rgba(255,255,0,1) 62.5%, rgba(255,0,0,1) 87.5%, rgba(128,0,0,1) 100%)"
    # grad_numbr = 9
    # gradient_string = "rgba(0,0,0,1) 0%, rgba(255,255,255,1) 70%, rgba(255,98,98,1) 87.5%, rgba(222,0,0,1) 100%)"
    # grad_numbr = 10
    # gradient_string = "rgba(255,255,255,1) 0%, rgba(0,0,0,1) 100%)"
    # split the string at the commas
    gradient_string = gradient_string.split(', ')

    for gradient_element in gradient_string:
        #split the color at the spaces
        gradient_element = gradient_element.split(' ')
        #split the color at the parentheses
        color = gradient_element[0].split('(')[1].split(')')[0].split(',')
        #convert the color to a numpy array
        color = np.array(color, dtype=np.float)
        #split the position at the percent sign
        position = gradient_element[1].split('%')[0]
        #convert the position to a float
        position = float(position) / 100
        #add the color to the gradient
        grad.add_color(color, position)
        print(color, position)



    lut = grad.get_lut(256)
    lut = lut.astype(np.uint8)

    save_location = './gradients'
    # convert np array to list and save as json under save_location
    lut_list = lut.tolist()
    with open(save_location + '/gradient_lut_'+str(grad_numbr)+'.json', 'w') as outfile:
        json.dump(lut_list, outfile)


    # print(lut)
    # for(i, color) in enumerate(lut):
    #     print(i, color)

    #show lut
    lut_image_gradient = np.zeros((150, lut.shape[0], 3), dtype=np.uint8)
    for i in range(0, 150):
        lut_image_gradient[i] = lut[:, 0:-1]

    plt.imshow(lut_image_gradient)
    plt.show()