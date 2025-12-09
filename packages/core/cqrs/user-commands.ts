import { connectDatabase } from "../database/database";
import { StudentLevel } from "../entities/student";
import { UserModel, User, FlashCardDisplayPreference } from "../entities/user";

export interface CreateUserData {
    name: string;
    email: string;
    level: StudentLevel;
}

export async function createUserCommand(userData: CreateUserData) {
    await connectDatabase();
    const user = new UserModel(userData);
    await user.save();
}

export interface UpdateFlashCardDisplayPreferenceData {
    userId: string;
    preference: FlashCardDisplayPreference;
}

export async function updateFlashCardDisplayPreferenceCommand(
    data: UpdateFlashCardDisplayPreferenceData,
): Promise<User | null> {
    await connectDatabase();

    const user = await UserModel.findByIdAndUpdate(
        data.userId,
        { flashCardDisplayPreference: data.preference },
        { new: true }
    );

    return user;
}