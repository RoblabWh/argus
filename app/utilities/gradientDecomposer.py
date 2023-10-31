import numpy as np
import cv2
from matplotlib import pyplot as plt


def load_image(path):
    return cv2.imread(path)

def crop_image_based_on_white_background(img):
    #iterate throug the middle pixel of each row
    #if the pixel is white, delete the row
    for i in range(0, int(img.shape[0]/2)):
        #print value of middle pixel of row
        print('from top', img[i, int(img.shape[1]/2)])
        if np.all(img[i, int(img.shape[1]/2)] == 255):
            img = np.delete(img, i, 0)
        else:
            break

    for i in range(img.shape[0]-1, int(img.shape[0]/2), -1):
        #print value of middle pixel of row
        print('from bottom',img[i, int(img.shape[1]/2)])
        if np.all(img[i, int(img.shape[1]/2)] == 255):
            img = np.delete(img, i, 0)
        else:
            break

    #iterate throug the middle pixel of each collumn
    #if the pixel is white, delete the row
    for i in range(0, int(img.shape[1]/2)):
        #print value of middle pixel of row
        print('from left', img[int(img.shape[0]/2), i])
        if np.all(img[int(img.shape[0]/2), i] == 255):
            img = np.delete(img, i, 1)
        else:
            break

    for i in range(img.shape[1]-1, int(img.shape[1]/2), -1):
        #print value of middle pixel of row
        print('from right', img[int(img.shape[0]/2), i])
        if np.all(img[int(img.shape[0]/2), i] == 255):
            img = np.delete(img, i, 1)
        else:
            break

    #crop image by 2 pixels on each side
    # img = img[2:-2, 2:-2]

    return img

if __name__ == '__main__':
    print(cv2.__version__)
    grad_nmbr = 3
    img = load_image('/home/max/Dokumente/DRZ-Programme/Gradient_extractor/gradient-screenshots/gradient_'+ str(grad_nmbr)+'.png')

    #show image

    img_cropped = crop_image_based_on_white_background(img)
    #save image
    cv2.imwrite('/home/max/Dokumente/DRZ-Programme/Gradient_extractor/gradient-screenshots/gradient_'+ str(grad_nmbr)+'_cropped.png', img_cropped)

    #display cropped an non cropped image in one window
    print(img_cropped.shape)

    #plot one line of img as graph with a line for red, green and blue
    red = img_cropped[int(img_cropped.shape[0]/2),:, 2]
    green = img_cropped[int(img_cropped.shape[0]/2),:, 1]
    blue = img_cropped[int(img_cropped.shape[0]/2),:, 0]

    x = np.arange(0, img_cropped.shape[1])


    #discard repeating values
    red_cleaned = red[0]
    green_cleaned = green[0]
    blue_cleaned = blue[0]
    for i in range(1, red.shape[0]):
        if red[i] != red[i-1]:
            red_cleaned = np.append(red_cleaned, red[i])
            green_cleaned = np.append(green_cleaned, green[i])
            blue_cleaned = np.append(blue_cleaned, blue[i])
        elif green[i] != green[i-1]:
            red_cleaned = np.append(red_cleaned, red[i])
            green_cleaned = np.append(green_cleaned, green[i])
            blue_cleaned = np.append(blue_cleaned, blue[i])
        elif blue[i] != blue[i-1]:
            red_cleaned = np.append(red_cleaned, red[i])
            green_cleaned = np.append(green_cleaned, green[i])
            blue_cleaned = np.append(blue_cleaned, blue[i])

    x_cleaned = np.arange(0, red_cleaned.shape[0])

    x_scaled = x / img_cropped.shape[1]

    #detect edges on red row
    # edges = cv2.convolution(red, np.array([[-1, 0, 1]]), borderType=cv2.BORDER_REPLICATE)


    #plot graph and show img and cropped image on top of each other

    img_channel_swapped = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img_cropped_channel_swapped = cv2.cvtColor(img_cropped, cv2.COLOR_BGR2RGB)

    fig = plt.figure()
    fig.add_subplot(4, 1, 1)
    plt.imshow(img_channel_swapped)
    fig.add_subplot(4, 1, 2)
    plt.imshow(img_cropped_channel_swapped)
    fig.add_subplot(4, 1, 3)
    plt.margins(x=0)
    plt.plot(x, red, 'r', x, green, 'g', x, blue, 'b')
    # plt.plot(x_cleaned, red_cleaned, 'r', x_cleaned, green_cleaned, 'g', x_cleaned, blue_cleaned, 'b')
    fig.add_subplot(4, 1, 4)
    plt.margins(x=0)
    # plt.plot(x, red, 'r', x, green, 'g', x, blue, 'b')
    plt.plot(x_scaled, red, 'r', x_scaled, green, 'g', x_scaled, blue, 'b')
    plt.show()





    # plt.plot(x, red, 'r', x, green, 'g', x, blue, 'b')
    # plt.imshow(img_cropped)
    # plt.show()


