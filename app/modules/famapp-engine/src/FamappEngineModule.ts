import { NativeModule, requireNativeModule } from "expo";

export type EngineInfo = {
  coreVersion: string;
  stringsBundled: boolean;
};

declare class FamappEngineModule extends NativeModule {
  engineInfo(): EngineInfo;
}

// Android only. The UI never imports this directly; it goes through app/data/repo.native.ts.
export default requireNativeModule<FamappEngineModule>("FamappEngine");
