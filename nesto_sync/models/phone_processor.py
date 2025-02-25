class PhoneProcessor:
    @staticmethod
    def process_phone_numbers(phone_numbers_str):
        """ Separa los números de teléfono en móvil, fijo y adicionales. """
        if not phone_numbers_str:
            return None, None, None

        phone_numbers = phone_numbers_str.split("/")
        mobile, phone, additional_phones = None, None, []

        for num in phone_numbers:
            clean_num = num.strip()
            if clean_num.startswith(("6", "7")) and not mobile:
                mobile = clean_num
            elif not clean_num.startswith(("6", "7")) and not phone:
                phone = clean_num
            else:
                additional_phones.append(clean_num)

        extra_phones = " / ".join(additional_phones) if additional_phones else None
        return mobile, phone, extra_phones
