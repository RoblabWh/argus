from .sorter import Sorter

class ImageTypeSorter(Sorter):

    def __init__(self):
        super(ImageTypeSorter, self).__init__()

    def filter_panos(self, images):
        panos = []
        rest_images = []
        for image in images:
            if image.get_exif_header().pano:
                panos.append(image)
            else:
                rest_images.append(image)

        return panos, rest_images

    def check_for_IR(self, images):
        if len(images) < 2:
            print("not enough Images provided")
            return False

        (width_0, height_0) = images[0].get_exif_header().get_image_size()
        for image in images[1:]:
            if image.get_exif_header().ir:
                print("Dataset contains IR Images, based on embedded Exif Data")
                return True
            else:
                (width_1, height_1) = image.get_exif_header().get_image_size()
                if width_0 != width_1 and height_0 != height_1:
                    print("Dataset seems to contain IR images, based on different image sizes")
                    return True

        return False


    def sort(self, images):
        images_1 = list()
        images_2 = list()
        infrared_images = None
        rgb_images = None

        (width, height) = images[0].get_exif_header().get_image_size()
        sorting_kriteria = width

        for image in images:
            (width, height) = image.get_exif_header().get_image_size()
            if sorting_kriteria == width:
                images_1.append(image)
            else:
                images_2.append(image)

        (width_1, height_1) = images_1[0].get_exif_header().get_image_size()
        (width_2, height_2) = images_2[0].get_exif_header().get_image_size()

        if width_1 < width_2:
            (infrared_images, rgb_images) = (images_1, images_2)
        else:
            (infrared_images, rgb_images) = (images_2, images_1)

        for i, infrared_image in enumerate(infrared_images):
            infrared_image.set_to_ir()
            infrared_image.set_rgb_counterpart_path(rgb_images[i].get_image_path())
            # TODO ungleiche Anzahl an IR/ RGB Bildern verarbeiten können

        return (infrared_images, rgb_images)

