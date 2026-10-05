import { getBackendConfig } from './index';
import { getSessionUser } from './auths';

// Keep the session result separate: a failed login must not hide the public
// configuration needed by the sign-in page.
export const loadInitialState = async (token: string | null) => {
	const configRequest = getBackendConfig();
	const session = token
		? getSessionUser(token).then(
				(user) => ({ user, error: null }),
				(error: unknown) => ({ user: null, error })
			)
		: { user: null, error: null };
	const [backendConfig, sessionResult] = await Promise.all([configRequest, session]);
	return { backendConfig, session: sessionResult };
};
