import { Id, toast } from 'react-toastify';

export const errorToast = (message: string): Id => {
  return toast.error(message, {
    position: 'top-right', // default position as well
    autoClose: 3000,
    hideProgressBar: true,
  });
};

export const successToast = (message: string): Id => {
  return toast.success(message, {
    position: 'top-right', // default position as well
    autoClose: 3000,
    hideProgressBar: true,
  });
};

export const warnToast = (message: string): Id => {
  return toast.warn(message, {
    position: 'top-right', // default position as well
    autoClose: 3000,
    hideProgressBar: true,
  });
};

export const permanentToast = (message: string): Id => {
  return toast.info(message, {
    position: 'top-right', // default position as well
    hideProgressBar: true,
    autoClose: false,
    closeButton: undefined,
    closeOnClick: true,
  });
};

export const closeToast = (id: Id) => {
  toast.dismiss(id);
};
